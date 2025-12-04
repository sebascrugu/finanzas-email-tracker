"""API Router para Patrimonio - Accounts, Investments, Goals, Snapshots.

Endpoints para gestionar el patrimonio neto del usuario.
"""

from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from finanzas_tracker.api.dependencies import get_db
from finanzas_tracker.api.schemas.patrimony import (
    AccountCreate,
    AccountResponse,
    AccountUpdate,
    AssetBreakdownResponse,
    GoalContribution,
    GoalCreate,
    GoalResponse,
    GoalsProgressResponse,
    GoalUpdate,
    InvestmentCreate,
    InvestmentResponse,
    InvestmentReturnsResponse,
    InvestmentUpdate,
    NetWorthResponse,
)
from finanzas_tracker.api.schemas.reconciliation import (
    PatrimonioSnapshotCreate,
    PatrimonioSnapshotResponse,
)
from finanzas_tracker.models.account import Account
from finanzas_tracker.models.enums import (
    AccountType,
    BankName,
    Currency,
    GoalPriority,
    GoalStatus,
    InvestmentType,
)
from finanzas_tracker.models.goal import Goal
from finanzas_tracker.models.investment import Investment
from finanzas_tracker.services.patrimony_service import PatrimonyService


router = APIRouter(prefix="/patrimony", tags=["Patrimonio"])


# =============================================================================
# Net Worth / Summary Endpoints
# =============================================================================


@router.get("/summary", response_model=NetWorthResponse)
def get_net_worth_summary(
    profile_id: str = Query(..., description="ID del perfil"),
    exchange_rate: Decimal | None = Query(None, description="Tipo de cambio USD/CRC"),
    db: Session = Depends(get_db),
) -> NetWorthResponse:
    """Obtiene el resumen de patrimonio neto.

    Calcula el total de activos combinando cuentas, inversiones y metas.
    """
    service = PatrimonyService(db)
    summary = service.calculate_net_worth(profile_id, exchange_rate)

    return NetWorthResponse(
        total_crc=summary.total_crc,
        total_usd=summary.total_usd,
        total_crc_equivalente=summary.total_crc_equivalente,
        breakdown=AssetBreakdownResponse(
            cuentas_crc=summary.breakdown.cuentas_crc,
            cuentas_usd=summary.breakdown.cuentas_usd,
            inversiones_crc=summary.breakdown.inversiones_crc,
            inversiones_usd=summary.breakdown.inversiones_usd,
            metas_crc=summary.breakdown.metas_crc,
            metas_usd=summary.breakdown.metas_usd,
            total_crc=summary.breakdown.total_crc,
            total_usd=summary.breakdown.total_usd,
        ),
        num_cuentas=summary.num_cuentas,
        num_inversiones=summary.num_inversiones,
        num_metas=summary.num_metas,
        fecha_calculo=summary.fecha_calculo,
    )


@router.get("/history")
def get_patrimony_history(
    profile_id: str = Query(..., description="ID del perfil"),
    meses: int = Query(6, ge=1, le=24, description="Meses de historial"),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Obtiene el historial de evolución del patrimonio.

    Retorna snapshots del patrimonio neto a lo largo del tiempo
    para graficar la evolución.
    """
    from datetime import date, timedelta
    
    service = PatrimonyService(db)
    
    # Calcular rango de fechas
    fecha_fin = date.today()
    fecha_inicio = fecha_fin - timedelta(days=meses * 30)
    
    snapshots = service.obtener_historial(
        profile_id=profile_id,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        limite=meses * 4,  # Aproximadamente 4 snapshots por mes
    )
    
    history = []
    for snapshot in snapshots:
        history.append({
            "fecha": snapshot.fecha_snapshot.isoformat(),
            "net_worth": float(snapshot.patrimonio_neto_crc),
            "activos": float(snapshot.total_activos_crc),
            "pasivos": float(snapshot.total_pasivos_crc),
        })
    
    # Ordenar por fecha ascendente
    history.sort(key=lambda x: x["fecha"])
    
    return history


@router.get("/returns", response_model=InvestmentReturnsResponse)
def get_investment_returns(
    profile_id: str = Query(..., description="ID del perfil"),
    db: Session = Depends(get_db),
) -> InvestmentReturnsResponse:
    """Obtiene los rendimientos totales de inversiones."""
    service = PatrimonyService(db)
    returns = service.get_investment_returns(profile_id)
    return InvestmentReturnsResponse(**returns)


@router.get("/goals-progress", response_model=GoalsProgressResponse)
def get_goals_progress(
    profile_id: str = Query(..., description="ID del perfil"),
    db: Session = Depends(get_db),
) -> GoalsProgressResponse:
    """Obtiene el progreso general de todas las metas."""
    service = PatrimonyService(db)
    progress = service.get_goals_progress(profile_id)
    return GoalsProgressResponse(**progress)


# =============================================================================
# Account CRUD Endpoints
# =============================================================================


@router.get("/accounts", response_model=list[AccountResponse])
def list_accounts(
    profile_id: str = Query(..., description="ID del perfil"),
    db: Session = Depends(get_db),
) -> list[AccountResponse]:
    """Lista todas las cuentas de un perfil."""
    stmt = select(Account).where(
        Account.profile_id == profile_id,
        Account.deleted_at.is_(None),
    ).order_by(Account.es_cuenta_principal.desc(), Account.nombre)

    result = db.execute(stmt)
    return [AccountResponse.model_validate(a) for a in result.scalars().all()]


@router.post("/accounts", response_model=AccountResponse, status_code=201)
def create_account(
    profile_id: str,
    data: AccountCreate,
    db: Session = Depends(get_db),
) -> AccountResponse:
    """Crea una nueva cuenta bancaria."""
    # Validar enums
    try:
        banco = BankName(data.banco)
        tipo = AccountType(data.tipo)
        moneda = Currency(data.moneda)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={"error": str(e), "code": "INVALID_ENUM"},
        )

    account = Account(
        profile_id=profile_id,
        banco=banco,
        tipo=tipo,
        nombre=data.nombre,
        numero_cuenta=data.numero_cuenta,
        saldo=data.saldo,
        moneda=moneda,
        saldo_minimo=data.saldo_minimo,
        es_cuenta_principal=data.es_cuenta_principal,
        incluir_en_patrimonio=data.incluir_en_patrimonio,
        notas=data.notas,
    )

    db.add(account)
    db.commit()
    db.refresh(account)

    return AccountResponse.model_validate(account)


@router.get("/accounts/{account_id}", response_model=AccountResponse)
def get_account(
    account_id: str,
    db: Session = Depends(get_db),
) -> AccountResponse:
    """Obtiene una cuenta por ID."""
    stmt = select(Account).where(
        Account.id == account_id,
        Account.deleted_at.is_(None),
    )
    account = db.execute(stmt).scalar_one_or_none()

    if not account:
        raise HTTPException(
            status_code=404,
            detail={"error": "Account not found", "code": "ACCOUNT_NOT_FOUND"},
        )

    return AccountResponse.model_validate(account)


@router.patch("/accounts/{account_id}", response_model=AccountResponse)
def update_account(
    account_id: str,
    data: AccountUpdate,
    db: Session = Depends(get_db),
) -> AccountResponse:
    """Actualiza una cuenta."""
    stmt = select(Account).where(
        Account.id == account_id,
        Account.deleted_at.is_(None),
    )
    account = db.execute(stmt).scalar_one_or_none()

    if not account:
        raise HTTPException(
            status_code=404,
            detail={"error": "Account not found", "code": "ACCOUNT_NOT_FOUND"},
        )

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(account, field, value)

    db.commit()
    db.refresh(account)

    return AccountResponse.model_validate(account)


@router.delete("/accounts/{account_id}", status_code=204)
def delete_account(
    account_id: str,
    db: Session = Depends(get_db),
) -> None:
    """Elimina una cuenta (soft delete)."""
    stmt = select(Account).where(
        Account.id == account_id,
        Account.deleted_at.is_(None),
    )
    account = db.execute(stmt).scalar_one_or_none()

    if not account:
        raise HTTPException(
            status_code=404,
            detail={"error": "Account not found", "code": "ACCOUNT_NOT_FOUND"},
        )

    account.deleted_at = datetime.utcnow()
    db.commit()


# =============================================================================
# Investment CRUD Endpoints
# =============================================================================


@router.get("/investments", response_model=list[InvestmentResponse])
def list_investments(
    profile_id: str = Query(..., description="ID del perfil"),
    include_inactive: bool = Query(False, description="Incluir inversiones inactivas"),
    db: Session = Depends(get_db),
) -> list[InvestmentResponse]:
    """Lista todas las inversiones de un perfil."""
    stmt = select(Investment).where(
        Investment.profile_id == profile_id,
        Investment.deleted_at.is_(None),
    )

    if not include_inactive:
        stmt = stmt.where(Investment.activa.is_(True))

    stmt = stmt.order_by(Investment.fecha_vencimiento)
    result = db.execute(stmt)

    investments = []
    for inv in result.scalars().all():
        response = InvestmentResponse.model_validate(inv)
        response.valor_actual = inv.valor_actual
        response.dias_para_vencimiento = inv.dias_para_vencimiento
        investments.append(response)

    return investments


@router.post("/investments", response_model=InvestmentResponse, status_code=201)
def create_investment(
    profile_id: str,
    data: InvestmentCreate,
    db: Session = Depends(get_db),
) -> InvestmentResponse:
    """Crea una nueva inversión."""
    # Validar enums
    try:
        tipo = InvestmentType(data.tipo)
        moneda = Currency(data.moneda)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={"error": str(e), "code": "INVALID_ENUM"},
        )

    investment = Investment(
        profile_id=profile_id,
        tipo=tipo,
        institucion=data.institucion,
        nombre=data.nombre,
        monto_principal=data.monto_principal,
        moneda=moneda,
        tasa_interes_anual=data.tasa_interes_anual,
        fecha_inicio=data.fecha_inicio,
        fecha_vencimiento=data.fecha_vencimiento,
        notas=data.notas,
        activa=data.activa,
        incluir_en_patrimonio=data.incluir_en_patrimonio,
    )

    db.add(investment)
    db.commit()
    db.refresh(investment)

    response = InvestmentResponse.model_validate(investment)
    response.valor_actual = investment.valor_actual
    response.dias_para_vencimiento = investment.dias_para_vencimiento
    return response


@router.get("/investments/{investment_id}", response_model=InvestmentResponse)
def get_investment(
    investment_id: str,
    db: Session = Depends(get_db),
) -> InvestmentResponse:
    """Obtiene una inversión por ID."""
    stmt = select(Investment).where(
        Investment.id == investment_id,
        Investment.deleted_at.is_(None),
    )
    investment = db.execute(stmt).scalar_one_or_none()

    if not investment:
        raise HTTPException(
            status_code=404,
            detail={"error": "Investment not found", "code": "INVESTMENT_NOT_FOUND"},
        )

    response = InvestmentResponse.model_validate(investment)
    response.valor_actual = investment.valor_actual
    response.dias_para_vencimiento = investment.dias_para_vencimiento
    return response


@router.patch("/investments/{investment_id}", response_model=InvestmentResponse)
def update_investment(
    investment_id: str,
    data: InvestmentUpdate,
    db: Session = Depends(get_db),
) -> InvestmentResponse:
    """Actualiza una inversión."""
    stmt = select(Investment).where(
        Investment.id == investment_id,
        Investment.deleted_at.is_(None),
    )
    investment = db.execute(stmt).scalar_one_or_none()

    if not investment:
        raise HTTPException(
            status_code=404,
            detail={"error": "Investment not found", "code": "INVESTMENT_NOT_FOUND"},
        )

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(investment, field, value)

    db.commit()
    db.refresh(investment)

    response = InvestmentResponse.model_validate(investment)
    response.valor_actual = investment.valor_actual
    response.dias_para_vencimiento = investment.dias_para_vencimiento
    return response


@router.delete("/investments/{investment_id}", status_code=204)
def delete_investment(
    investment_id: str,
    db: Session = Depends(get_db),
) -> None:
    """Elimina una inversión (soft delete)."""
    stmt = select(Investment).where(
        Investment.id == investment_id,
        Investment.deleted_at.is_(None),
    )
    investment = db.execute(stmt).scalar_one_or_none()

    if not investment:
        raise HTTPException(
            status_code=404,
            detail={"error": "Investment not found", "code": "INVESTMENT_NOT_FOUND"},
        )

    investment.deleted_at = datetime.utcnow()
    db.commit()


# =============================================================================
# Goal CRUD Endpoints
# =============================================================================


@router.get("/goals", response_model=list[GoalResponse])
def list_goals(
    profile_id: str = Query(..., description="ID del perfil"),
    only_active: bool = Query(True, description="Solo metas activas"),
    db: Session = Depends(get_db),
) -> list[GoalResponse]:
    """Lista todas las metas de un perfil."""
    stmt = select(Goal).where(
        Goal.profile_id == profile_id,
        Goal.deleted_at.is_(None),
    )

    if only_active:
        stmt = stmt.where(Goal.estado == GoalStatus.ACTIVA)

    stmt = stmt.order_by(Goal.prioridad, Goal.fecha_objetivo)
    result = db.execute(stmt)

    goals = []
    for goal in result.scalars().all():
        response = GoalResponse.model_validate(goal)
        response.porcentaje_completado = goal.porcentaje_completado
        response.monto_faltante = goal.monto_faltante
        response.dias_restantes = goal.dias_restantes
        goals.append(response)

    return goals


@router.post("/goals", response_model=GoalResponse, status_code=201)
def create_goal(
    profile_id: str,
    data: GoalCreate,
    db: Session = Depends(get_db),
) -> GoalResponse:
    """Crea una nueva meta financiera."""
    # Validar enums
    try:
        moneda = Currency(data.moneda)
        prioridad = GoalPriority(data.prioridad)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={"error": str(e), "code": "INVALID_ENUM"},
        )

    goal = Goal(
        profile_id=profile_id,
        nombre=data.nombre,
        descripcion=data.descripcion,
        monto_objetivo=data.monto_objetivo,
        monto_actual=data.monto_actual,
        moneda=moneda,
        fecha_objetivo=data.fecha_objetivo,
        prioridad=prioridad,
        estado=GoalStatus.ACTIVA,
        icono=data.icono,
    )

    db.add(goal)
    db.commit()
    db.refresh(goal)

    response = GoalResponse.model_validate(goal)
    response.porcentaje_completado = goal.porcentaje_completado
    response.monto_faltante = goal.monto_faltante
    response.dias_restantes = goal.dias_restantes
    return response


@router.get("/goals/{goal_id}", response_model=GoalResponse)
def get_goal(
    goal_id: str,
    db: Session = Depends(get_db),
) -> GoalResponse:
    """Obtiene una meta por ID."""
    stmt = select(Goal).where(
        Goal.id == goal_id,
        Goal.deleted_at.is_(None),
    )
    goal = db.execute(stmt).scalar_one_or_none()

    if not goal:
        raise HTTPException(
            status_code=404,
            detail={"error": "Goal not found", "code": "GOAL_NOT_FOUND"},
        )

    response = GoalResponse.model_validate(goal)
    response.porcentaje_completado = goal.porcentaje_completado
    response.monto_faltante = goal.monto_faltante
    response.dias_restantes = goal.dias_restantes
    return response


@router.patch("/goals/{goal_id}", response_model=GoalResponse)
def update_goal(
    goal_id: str,
    data: GoalUpdate,
    db: Session = Depends(get_db),
) -> GoalResponse:
    """Actualiza una meta."""
    stmt = select(Goal).where(
        Goal.id == goal_id,
        Goal.deleted_at.is_(None),
    )
    goal = db.execute(stmt).scalar_one_or_none()

    if not goal:
        raise HTTPException(
            status_code=404,
            detail={"error": "Goal not found", "code": "GOAL_NOT_FOUND"},
        )

    update_data = data.model_dump(exclude_unset=True)

    # Convertir enums si están presentes
    if "prioridad" in update_data:
        try:
            update_data["prioridad"] = GoalPriority(update_data["prioridad"])
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail={"error": str(e), "code": "INVALID_ENUM"},
            )

    if "estado" in update_data:
        try:
            update_data["estado"] = GoalStatus(update_data["estado"])
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail={"error": str(e), "code": "INVALID_ENUM"},
            )

    for field, value in update_data.items():
        setattr(goal, field, value)

    db.commit()
    db.refresh(goal)

    response = GoalResponse.model_validate(goal)
    response.porcentaje_completado = goal.porcentaje_completado
    response.monto_faltante = goal.monto_faltante
    response.dias_restantes = goal.dias_restantes
    return response


@router.post("/goals/{goal_id}/contribute", response_model=GoalResponse)
def add_goal_contribution(
    goal_id: str,
    data: GoalContribution,
    db: Session = Depends(get_db),
) -> GoalResponse:
    """Agrega una contribución a una meta."""
    stmt = select(Goal).where(
        Goal.id == goal_id,
        Goal.deleted_at.is_(None),
    )
    goal = db.execute(stmt).scalar_one_or_none()

    if not goal:
        raise HTTPException(
            status_code=404,
            detail={"error": "Goal not found", "code": "GOAL_NOT_FOUND"},
        )

    if goal.estado != GoalStatus.ACTIVA:
        raise HTTPException(
            status_code=400,
            detail={"error": "Cannot contribute to inactive goal", "code": "GOAL_INACTIVE"},
        )

    goal.agregar_monto(data.monto)
    db.commit()
    db.refresh(goal)

    response = GoalResponse.model_validate(goal)
    response.porcentaje_completado = goal.porcentaje_completado
    response.monto_faltante = goal.monto_faltante
    response.dias_restantes = goal.dias_restantes
    return response


@router.delete("/goals/{goal_id}", status_code=204)
def delete_goal(
    goal_id: str,
    db: Session = Depends(get_db),
) -> None:
    """Elimina una meta (soft delete)."""
    stmt = select(Goal).where(
        Goal.id == goal_id,
        Goal.deleted_at.is_(None),
    )
    goal = db.execute(stmt).scalar_one_or_none()

    if not goal:
        raise HTTPException(
            status_code=404,
            detail={"error": "Goal not found", "code": "GOAL_NOT_FOUND"},
        )

    goal.deleted_at = datetime.utcnow()
    db.commit()


# =============================================================================
# Patrimonio Snapshot Endpoints
# =============================================================================


@router.post("/snapshots", response_model=PatrimonioSnapshotResponse, status_code=201)
def crear_snapshot(
    profile_id: str = Query(..., description="ID del perfil"),
    fecha: date | None = Query(None, description="Fecha del snapshot (default: hoy)"),
    exchange_rate: Decimal | None = Query(None, description="Tipo de cambio USD/CRC"),
    notas: str | None = Query(None, description="Notas opcionales"),
    db: Session = Depends(get_db),
) -> PatrimonioSnapshotResponse:
    """Crea un snapshot del patrimonio actual.

    Captura el estado de cuentas e inversiones en un momento dado.
    """
    service = PatrimonyService(db)
    snapshot = service.crear_snapshot(
        profile_id=profile_id,
        fecha=fecha,
        exchange_rate=exchange_rate,
        notas=notas,
    )
    return PatrimonioSnapshotResponse.model_validate(snapshot)


@router.post("/snapshots/inicial", response_model=PatrimonioSnapshotResponse, status_code=201)
def establecer_patrimonio_inicial(
    profile_id: str = Query(..., description="ID del perfil"),
    fecha_base: date = Query(..., description="Fecha de inicio del tracking (FECHA_BASE)"),
    exchange_rate: Decimal | None = Query(None, description="Tipo de cambio USD/CRC"),
    notas: str | None = Query(None, description="Notas opcionales"),
    db: Session = Depends(get_db),
) -> PatrimonioSnapshotResponse:
    """Establece el patrimonio inicial (FECHA_BASE).

    Este es el punto de partida para el tracking de patrimonio.
    Solo puede existir un snapshot de fecha base por perfil.
    """
    service = PatrimonyService(db)
    try:
        snapshot = service.establecer_patrimonio_inicial(
            profile_id=profile_id,
            fecha_base=fecha_base,
            exchange_rate=exchange_rate,
            notas=notas,
        )
        return PatrimonioSnapshotResponse.model_validate(snapshot)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={"error": str(e), "code": "FECHA_BASE_EXISTS"},
        )


@router.get("/snapshots/historial", response_model=list[PatrimonioSnapshotResponse])
def obtener_historial_snapshots(
    profile_id: str = Query(..., description="ID del perfil"),
    fecha_inicio: date | None = Query(None, description="Fecha inicio del rango"),
    fecha_fin: date | None = Query(None, description="Fecha fin del rango"),
    limite: int = Query(12, ge=1, le=100, description="Máximo de snapshots a retornar"),
    db: Session = Depends(get_db),
) -> list[PatrimonioSnapshotResponse]:
    """Obtiene el historial de snapshots de patrimonio.

    Útil para ver la evolución del patrimonio en el tiempo.
    """
    service = PatrimonyService(db)
    snapshots = service.obtener_historial(
        profile_id=profile_id,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        limite=limite,
    )
    return [PatrimonioSnapshotResponse.model_validate(s) for s in snapshots]


@router.get("/snapshots/ultimo", response_model=PatrimonioSnapshotResponse | None)
def obtener_ultimo_snapshot(
    profile_id: str = Query(..., description="ID del perfil"),
    db: Session = Depends(get_db),
) -> PatrimonioSnapshotResponse | None:
    """Obtiene el snapshot más reciente."""
    service = PatrimonyService(db)
    snapshot = service.get_ultimo_snapshot(profile_id)
    if snapshot:
        return PatrimonioSnapshotResponse.model_validate(snapshot)
    return None


@router.get("/snapshots/fecha-base", response_model=PatrimonioSnapshotResponse | None)
def obtener_snapshot_fecha_base(
    profile_id: str = Query(..., description="ID del perfil"),
    db: Session = Depends(get_db),
) -> PatrimonioSnapshotResponse | None:
    """Obtiene el snapshot de fecha base (patrimonio inicial)."""
    service = PatrimonyService(db)
    snapshot = service.get_snapshot_fecha_base(profile_id)
    if snapshot:
        return PatrimonioSnapshotResponse.model_validate(snapshot)
    return None


@router.get("/snapshots/cambio-periodo")
def calcular_cambio_periodo(
    profile_id: str = Query(..., description="ID del perfil"),
    fecha_inicio: date = Query(..., description="Fecha inicio del periodo"),
    fecha_fin: date = Query(..., description="Fecha fin del periodo"),
    db: Session = Depends(get_db),
) -> dict:
    """Calcula el cambio de patrimonio entre dos fechas.

    Retorna el cambio absoluto y porcentual del patrimonio.
    """
    service = PatrimonyService(db)
    try:
        return service.calcular_cambio_periodo(
            profile_id=profile_id,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={"error": str(e), "code": "INSUFFICIENT_DATA"},
        )


@router.post("/snapshots/mensual", response_model=PatrimonioSnapshotResponse | None)
def generar_snapshot_mensual(
    profile_id: str = Query(..., description="ID del perfil"),
    exchange_rate: Decimal | None = Query(None, description="Tipo de cambio USD/CRC"),
    db: Session = Depends(get_db),
) -> PatrimonioSnapshotResponse | None:
    """Genera snapshot mensual si no existe uno este mes.

    Útil para automatizar la captura mensual de patrimonio.
    Retorna None si ya existe un snapshot este mes.
    """
    service = PatrimonyService(db)
    snapshot = service.generar_snapshot_mensual(
        profile_id=profile_id,
        exchange_rate=exchange_rate,
    )
    if snapshot:
        return PatrimonioSnapshotResponse.model_validate(snapshot)
    return None
