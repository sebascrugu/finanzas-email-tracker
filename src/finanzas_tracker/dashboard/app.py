"""
App principal de Streamlit - Dashboard de Finanzas Simplificado.

Esta es la página principal que se muestra al usuario.
"""

import calendar
import time
from collections import defaultdict
from datetime import date

import pandas as pd
import streamlit as st


# Configurar página
st.set_page_config(
    page_title="Dashboard - Finanzas Tracker",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={
        "Get Help": None,
        "Report a bug": None,
        "About": "Finanzas Email Tracker - Sistema automatizado de rastreo financiero",
    },
)

# CSS personalizado - Solo estilos específicos del diseño
# El tema base se configura en .streamlit/config.toml
st.markdown(
    """
    <style>
    /* Layout y espaciado */
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 1200px;
    }

    /* Hero metric - Card destacada con gradiente */
    .hero-metric {
        text-align: center;
        padding: 2.5rem 1rem;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 16px;
        margin-bottom: 2rem;
        box-shadow: 0 4px 20px rgba(102, 126, 234, 0.25);
    }

    .hero-metric h1 {
        color: white;
        font-size: 3.5rem;
        font-weight: 700;
        margin: 0;
        letter-spacing: -1px;
    }

    .hero-metric p {
        color: rgba(255, 255, 255, 0.95);
        font-size: 1.1rem;
        margin: 0.5rem 0 0 0;
        font-weight: 400;
    }

    /* Metric cards - Diseño mejorado */
    div[data-testid="metric-container"] {
        border-radius: 12px;
        padding: 1.25rem 1rem;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
        transition: all 0.2s ease;
    }

    div[data-testid="metric-container"]:hover {
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        transform: translateY(-2px);
    }

    div[data-testid="stMetricLabel"] {
        font-size: 0.85rem;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    div[data-testid="stMetricValue"] {
        font-size: 1.75rem;
        font-weight: 700;
    }

    /* Botones con mejor interacción */
    .stButton>button {
        border-radius: 10px;
        font-weight: 600;
        padding: 0.6rem 1.2rem;
        transition: all 0.2s ease;
        font-size: 0.9rem;
    }

    .stButton>button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
    }

    /* Barras de progreso con gradiente */
    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #10b981 0%, #059669 100%);
        border-radius: 10px;
    }

    /* Headers con mejor jerarquía */
    .main h3 {
        font-size: 1.25rem;
        margin-top: 2rem;
        margin-bottom: 1rem;
        font-weight: 700;
    }

    /* Dividers sutiles */
    .main hr {
        margin: 2rem 0;
        border: none;
        border-top: 1px solid rgba(0, 0, 0, 0.1);
    }

    /* Charts con bordes redondeados */
    .element-container iframe {
        border-radius: 12px;
    }

    /* Alerts con bordes redondeados */
    .stAlert {
        border-radius: 10px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Importar después de set_page_config
from pathlib import Path
import sys


# Agregar src al path
src_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(src_path))

import contextlib

from sqlalchemy.orm import joinedload

from finanzas_tracker.core.constants import (
    BUDGET_CAUTION_THRESHOLD,
    BUDGET_EXCEEDED_THRESHOLD,
    BUDGET_WARNING_THRESHOLD,
)
from finanzas_tracker.core.database import get_session, init_db
from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.models.account import Account
from finanzas_tracker.models.category import Subcategory
from finanzas_tracker.models.income import Income
from finanzas_tracker.models.pending_question import PendingQuestion, QuestionStatus
from finanzas_tracker.models.profile import Profile
from finanzas_tracker.models.transaction import Transaction
from finanzas_tracker.utils.seed_categories import seed_categories
from finanzas_tracker.utils.seed_merchants import seed_merchants
from finanzas_tracker.services.insights_service import InsightsService, InsightType


logger = get_logger(__name__)

# Inicializar BD
init_db()

# Seed categorías si no existen
seed_categories()

# Seed merchants si no existen
seed_merchants()


def get_active_profile() -> Profile | None:
    """Obtiene el perfil activo con todas sus relaciones cargadas."""
    with get_session() as session:
        perfil = (
            session.query(Profile)
            .options(
                joinedload(Profile.budgets),
                joinedload(Profile.cards),
            )
            .filter(
                Profile.es_activo == True,
                Profile.activo == True,
            )
            .first()
        )

        if perfil:
            # Forzar la carga de relaciones antes de cerrar la sesión
            _ = perfil.budgets
            _ = perfil.cards
            _ = perfil.bancos_asociados

        return perfil


def mostrar_sidebar_simple(perfil_actual: Profile) -> None:
    """Muestra sidebar minimalista - solo selector si hay múltiples perfiles."""
    with get_session() as session:
        perfiles = session.query(Profile).filter(Profile.activo == True).all()

        # Selector solo si hay múltiples perfiles
        if len(perfiles) > 1:
            st.sidebar.markdown("**Cambiar Perfil**")

            perfil_nombres = [f"{p.icono} {p.nombre}" for p in perfiles]
            perfil_ids = [p.id for p in perfiles]

            idx_actual = 0
            with contextlib.suppress(ValueError):
                idx_actual = perfil_ids.index(perfil_actual.id)

            seleccion = st.sidebar.selectbox(
                "Perfil:",
                options=range(len(perfiles)),
                format_func=lambda i: perfil_nombres[i],
                index=idx_actual,
                key="selector_perfil",
                label_visibility="collapsed",
            )

            # Si cambió el perfil, actualizar
            if perfil_ids[seleccion] != perfil_actual.id:
                nuevo_perfil = session.query(Profile).get(perfil_ids[seleccion])
                if nuevo_perfil:
                    # Desactivar todos los perfiles
                    for p in perfiles:
                        p.es_activo = False
                    # Activar el nuevo
                    nuevo_perfil.es_activo = True
                    session.commit()
                    st.rerun()


def ocultar_sidebar() -> None:
    """Oculta completamente el sidebar para pantallas sin login."""
    st.markdown(
        """
        <style>
        /* Ocultar sidebar completamente */
        [data-testid="stSidebar"] {
            display: none !important;
        }
        [data-testid="stSidebarNav"] {
            display: none !important;
        }
        /* Ocultar el botón de expandir sidebar */
        button[kind="header"] {
            display: none !important;
        }
        .css-1544g2n {
            display: none !important;
        }
        /* Expandir contenido principal */
        .main .block-container {
            max-width: 900px;
            margin: 0 auto;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def mostrar_pantalla_login() -> bool:
    """
    Muestra la pantalla de login/registro.
    Retorna True si el usuario se registró exitosamente.
    """
    ocultar_sidebar()
    
    st.markdown(
        """
        <div style='text-align: center; padding: 2rem 0 1rem 0;'>
            <h1 style='font-size: 4rem; margin-bottom: 0;'>💰</h1>
            <h1 style='font-size: 2.2rem; margin-bottom: 0.5rem; color: #1f1f1f;'>
                Finanzas Tracker
            </h1>
            <p style='font-size: 1.1rem; color: #666;'>
                Control financiero inteligente para Costa Rica
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Tabs para login y registro
    tab_login, tab_registro = st.tabs(["🔑 Iniciar Sesión", "✨ Registrarse"])
    
    with tab_login:
        st.markdown("### Ingresa a tu cuenta")
        
        with st.form("form_login"):
            email_login = st.text_input(
                "Email",
                placeholder="tu@email.com",
                key="login_email",
            )
            password_login = st.text_input(
                "Contraseña",
                type="password",
                placeholder="••••••••",
                key="login_password",
            )
            
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                submitted_login = st.form_submit_button(
                    "Iniciar Sesión",
                    type="primary",
                    use_container_width=True,
                )
            
            if submitted_login:
                if email_login and password_login:
                    # Buscar usuario existente
                    with get_session() as session:
                        perfil = session.query(Profile).filter(
                            Profile.email_outlook == email_login,
                            Profile.activo == True,
                        ).first()
                        
                        if perfil:
                            # TODO: Verificar contraseña cuando implementemos auth real
                            perfil.es_activo = True
                            session.commit()
                            st.success("¡Bienvenido de vuelta!")
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            st.error("No encontramos una cuenta con ese email. ¿Quieres registrarte?")
                else:
                    st.warning("Por favor completa todos los campos")
    
    with tab_registro:
        st.markdown("### Crea tu cuenta")
        st.markdown("*Solo necesitas un email para empezar*")
        
        with st.form("form_registro"):
            nombre = st.text_input(
                "Tu nombre",
                placeholder="Ej: Sebastián",
                key="registro_nombre",
            )
            email = st.text_input(
                "Tu email",
                placeholder="tu@gmail.com o tu@outlook.com",
                key="registro_email",
            )
            
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                submitted_registro = st.form_submit_button(
                    "🚀 Crear Mi Cuenta",
                    type="primary",
                    use_container_width=True,
                )
            
            if submitted_registro:
                if nombre and email:
                    # Validar email
                    if "@" not in email:
                        st.error("Por favor ingresa un email válido")
                    else:
                        # Verificar si ya existe
                        with get_session() as session:
                            existe = session.query(Profile).filter(
                                Profile.email_outlook == email,
                            ).first()
                            
                            if existe:
                                st.error("Ya existe una cuenta con ese email. Intenta iniciar sesión.")
                            else:
                                # Crear nuevo perfil
                                nuevo_perfil = Profile(
                                    nombre=nombre,
                                    email_outlook=email,
                                    icono="👤",
                                    es_activo=True,
                                    activo=True,
                                )
                                session.add(nuevo_perfil)
                                session.commit()
                                
                                # Detectar tipo de email y guardar para onboarding
                                email_lower = email.lower()
                                if any(d in email_lower for d in ["@outlook.", "@hotmail.", "@live.", "@msn."]):
                                    st.session_state["email_provider"] = "outlook"
                                elif "@gmail." in email_lower:
                                    st.session_state["email_provider"] = "gmail"
                                else:
                                    st.session_state["email_provider"] = "other"
                                
                                st.session_state["nuevo_perfil_id"] = nuevo_perfil.id
                                st.success("🎉 ¡Cuenta creada!")
                                time.sleep(0.5)
                                st.rerun()
                else:
                    st.warning("Por favor completa nombre y email")
        
        # Info adicional
        st.markdown("---")
        st.markdown(
            """
            <div style='text-align: center; color: #888; font-size: 0.85rem;'>
                <p>🔒 Tus datos están seguros y nunca los compartimos</p>
                <p>📧 Usamos OAuth de Microsoft/Google - nunca guardamos tu contraseña</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    return False


def _conectar_outlook(perfil: Profile) -> None:
    """Conecta Outlook y usa SyncStrategy para sincronización inteligente."""
    try:
        from finanzas_tracker.services.auth_manager import AuthManager
        
        # Container para mostrar progreso
        progress_container = st.container()
        
        with progress_container:
            # Paso 1: Conectar
            st.markdown("### 🔐 Conectando con tu cuenta...")
            progress_bar = st.progress(0, text="Iniciando conexión segura...")
            
            auth = AuthManager()
            progress_bar.progress(10, text="🌐 Abriendo ventana de autorización...")
            token = auth.get_access_token(interactive=True)
            
            if token:
                progress_bar.progress(25, text="✅ ¡Conectado! Preparando sincronización...")
                st.session_state["outlook_connected"] = True
                time.sleep(0.3)
                
                # Paso 2: Buscar PDFs
                progress_bar.progress(30, text="📄 Buscando estados de cuenta PDF...")
                st.markdown("""
                <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                            padding: 20px; border-radius: 15px; text-align: center; margin: 20px 0;'>
                    <h3 style='color: white; margin: 0;'>🔍 Analizando tu correo...</h3>
                    <p style='color: rgba(255,255,255,0.9); margin: 10px 0 0 0;'>
                        Esto puede tomar unos segundos. Estamos buscando tus estados de cuenta y notificaciones bancarias.
                    </p>
                </div>
                """, unsafe_allow_html=True)
                
                from finanzas_tracker.services.sync_strategy import SyncStrategy
                
                progress_bar.progress(40, text="📧 Escaneando correos de los últimos 31 días...")
                sync = SyncStrategy(profile_id=str(perfil.id))
                
                progress_bar.progress(50, text="🤖 Procesando y categorizando transacciones...")
                result = sync.onboarding_sync()
                
                progress_bar.progress(80, text="📊 Finalizando análisis...")
                time.sleep(0.3)
                
                if result.success:
                    progress_bar.progress(100, text="✅ ¡Sincronización completada!")
                    time.sleep(0.3)
                    progress_bar.empty()
                    
                    # Mostrar resultados bonitos
                    st.markdown("""
                    <div style='background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); 
                                padding: 25px; border-radius: 15px; text-align: center; margin: 20px 0;'>
                        <h2 style='color: white; margin: 0;'>🎉 ¡Sincronización Exitosa!</h2>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("📄 PDF", f"{result.pdf_transactions}", help="Transacciones del estado de cuenta")
                    with col2:
                        st.metric("📧 Correos", f"{result.email_transactions}", help="Notificaciones individuales")
                    with col3:
                        st.metric("📊 Total", f"{result.total_transactions}", help="Total importadas")
                    
                    _crear_tarjeta_placeholder(perfil)
                    st.balloons()
                    time.sleep(2)
                    st.rerun()
                else:
                    progress_bar.progress(100, text="⚠️ Sincronización parcial")
                    progress_bar.empty()
                    
                    if result.errors:
                        for error in result.errors:
                            st.warning(f"⚠️ {error}")
                    
                    if result.total_transactions == 0:
                        st.warning("📭 No se encontraron estados de cuenta en los últimos 31 días.")
                        _buscar_correos_individuales_outlook(perfil)
                    else:
                        st.success(f"✅ Importadas {result.total_transactions} transacciones (solo correos)")
                        _crear_tarjeta_placeholder(perfil)
                        st.balloons()
                        time.sleep(2)
                        st.rerun()
            else:
                progress_bar.empty()
                st.error("❌ No se pudo conectar. Intenta de nuevo.")
                
    except Exception as e:
        import traceback
        st.error(f"❌ Error: {e}")
        logger.error(f"Error en OAuth Outlook: {traceback.format_exc()}")


def _buscar_correos_recientes_outlook(perfil: Profile) -> int:
    """
    Busca correos de notificaciones recientes para complementar el PDF.
    Retorna el número de transacciones importadas.
    """
    from finanzas_tracker.services.email_fetcher import EmailFetcher
    from finanzas_tracker.services.transaction_processor import TransactionProcessor
    
    try:
        fetcher = EmailFetcher()
        # Solo últimos 30 días para obtener lo más reciente
        emails = fetcher.fetch_all_emails(days_back=30)
        
        if emails:
            processor = TransactionProcessor(auto_categorize=True)
            stats = processor.process_emails(emails, perfil.id)
            return stats.get("procesados", 0)
        return 0
    except Exception as e:
        logger.error(f"Error buscando correos recientes: {e}")
        return 0


def _buscar_correos_individuales_outlook(perfil: Profile) -> None:
    """Busca correos individuales de transacciones en Outlook."""
    from datetime import date
    
    # Calcular desde el 1er día del mes anterior
    hoy = date.today()
    if hoy.month == 1:
        primer_dia_mes_anterior = date(hoy.year - 1, 12, 1)
    else:
        primer_dia_mes_anterior = date(hoy.year, hoy.month - 1, 1)
    dias_atras = (hoy - primer_dia_mes_anterior).days
    
    st.markdown(f"""
    <div style='background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); 
                padding: 20px; border-radius: 15px; text-align: center; margin: 20px 0;'>
        <h3 style='color: white; margin: 0;'>💡 Plan B: Notificaciones Individuales</h3>
        <p style='color: rgba(255,255,255,0.9); margin: 10px 0 0 0;'>
            Buscando correos desde {primer_dia_mes_anterior.strftime('%d/%m/%Y')}...
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    from finanzas_tracker.services.email_fetcher import EmailFetcher
    from finanzas_tracker.services.transaction_processor import TransactionProcessor
    
    progress_bar = st.progress(0, text=f"🔍 Buscando correos desde {primer_dia_mes_anterior.strftime('%d/%m')}...")
    
    fetcher = EmailFetcher()
    progress_bar.progress(30, text="📧 Escaneando bandeja de entrada...")
    emails = fetcher.fetch_all_emails(days_back=dias_atras)
    
    if emails:
        progress_bar.progress(50, text=f"📬 ¡Encontrados {len(emails)} correos! Procesando...")
        st.success(f"📬 Encontrados {len(emails)} correos de notificaciones!")
        
        progress_bar.progress(70, text="🤖 Categorizando transacciones...")
        processor = TransactionProcessor(auto_categorize=False)
        stats = processor.process_emails(emails, perfil.id)
        
        progress_bar.progress(100, text="✅ ¡Listo!")
        time.sleep(0.3)
        progress_bar.empty()
        
        if stats["procesados"] > 0:
            st.markdown(f"""
            <div style='background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); 
                        padding: 25px; border-radius: 15px; text-align: center; margin: 20px 0;'>
                <h2 style='color: white; margin: 0;'>✅ ¡Importadas {stats['procesados']} transacciones!</h2>
            </div>
            """, unsafe_allow_html=True)
            _crear_tarjeta_placeholder(perfil)
            st.balloons()
            time.sleep(2)
            st.rerun()
        else:
            st.warning("Los correos no contenían transacciones válidas.")
    else:
        progress_bar.empty()
        st.warning("📭 No se encontraron correos bancarios.")
        st.info("💡 Usa la opción de subir PDF manualmente.")


def _conectar_gmail(perfil: Profile) -> None:
    """Conecta Gmail y busca estados de cuenta."""
    try:
        from finanzas_tracker.services.gmail_auth_manager import GmailAuthManager
        
        gmail_auth = GmailAuthManager()
        
        if not gmail_auth.is_configured():
            st.error("❌ Gmail no está configurado. Falta GOOGLE_CLIENT_ID en .env")
            return
        
        with st.spinner("🌐 Conectando con Gmail..."):
            creds = gmail_auth.get_credentials(interactive=True)
            
            if creds:
                user_email = gmail_auth.get_current_user_email()
                st.success(f"✅ ¡Gmail conectado! ({user_email})")
                st.session_state["gmail_connected"] = True
                time.sleep(0.5)
                
                # Buscar estados de cuenta (PDFs)
                st.info("📄 Buscando estados de cuenta de los últimos 60 días...")
                from finanzas_tracker.services.gmail_email_fetcher import GmailEmailFetcher
                
                fetcher = GmailEmailFetcher()
                statements = fetcher.fetch_statement_emails(days_back=60)
                
                if statements:
                    st.success(f"📬 Encontrados {len(statements)} estados de cuenta!")
                    
                    for stmt in statements:
                        st.write(f"📄 **{stmt.statement_type}**: {stmt.attachment_name} ({stmt.received_date.strftime('%d/%m/%Y')})")
                    
                    st.info("🔄 Procesando el más reciente...")
                    # TODO: Procesar PDF de Gmail (similar a Outlook)
                    st.warning("⚠️ Procesamiento de PDF de Gmail próximamente...")
                else:
                    st.warning("📭 No se encontraron estados de cuenta.")
                    _buscar_correos_individuales_gmail(perfil)
            else:
                st.error("❌ No se pudo conectar. Intenta de nuevo.")
                
    except Exception as e:
        import traceback
        st.error(f"❌ Error: {e}")
        logger.error(f"Error en OAuth Gmail: {traceback.format_exc()}")


def _buscar_correos_individuales_gmail(perfil: Profile) -> None:
    """Busca correos individuales de transacciones en Gmail."""
    st.info("💡 Buscaremos correos de notificaciones individuales (últimos 31 días)...")
    
    from finanzas_tracker.services.gmail_email_fetcher import GmailEmailFetcher
    
    fetcher = GmailEmailFetcher()
    emails = fetcher.fetch_bank_emails(days_back=31)
    
    if emails:
        st.success(f"📬 Encontrados {len(emails)} correos bancarios!")
        # TODO: Procesar correos de Gmail
        st.warning("⚠️ Procesamiento de correos Gmail próximamente...")
    else:
        st.warning("📭 No se encontraron correos bancarios.")
        st.info("💡 Usa la opción de subir PDF manualmente.")


def _detectar_proveedor_email(email: str) -> str:
    """Detecta el proveedor de email (outlook, gmail, other)."""
    email_lower = email.lower()
    if any(d in email_lower for d in ["@outlook.", "@hotmail.", "@live.", "@msn."]):
        return "outlook"
    elif "@gmail." in email_lower:
        return "gmail"
    return "other"


def contar_items_pendientes_revision(profile_id: str) -> dict:
    """
    Cuenta cuántos ítems necesitan revisión antes de mostrar el dashboard.
    Incluye: SINPE, tarjetas, compras, ingresos - todo lo confuso.
    
    Returns:
        Dict con conteos por tipo y total
    """
    with get_session() as session:
        # 1. SINPE/Transferencias que necesitan reconciliación
        transferencias_confusas = session.query(Transaction).filter(
            Transaction.profile_id == profile_id,
            Transaction.necesita_reconciliacion_sinpe == True,
            Transaction.deleted_at.is_(None),
        ).count()
        
        # 2. Comercios ambiguos (pueden ser de varias categorías)
        comercios_ambiguos = session.query(Transaction).filter(
            Transaction.profile_id == profile_id,
            Transaction.es_comercio_ambiguo == True,
            Transaction.deleted_at.is_(None),
        ).count()
        
        # 3. Compras/Gastos de tarjeta sin categoría
        compras_sin_categoria = session.query(Transaction).filter(
            Transaction.profile_id == profile_id,
            Transaction.subcategory_id.is_(None),
            Transaction.tipo_transaccion == "PURCHASE",
            Transaction.excluir_de_presupuesto == False,
            Transaction.deleted_at.is_(None),
        ).count()
        
        # 4. Transferencias sin categoría (que no son SINPE confusos)
        transferencias_sin_categoria = session.query(Transaction).filter(
            Transaction.profile_id == profile_id,
            Transaction.subcategory_id.is_(None),
            Transaction.tipo_transaccion == "TRANSFER",
            Transaction.necesita_reconciliacion_sinpe == False,
            Transaction.excluir_de_presupuesto == False,
            Transaction.deleted_at.is_(None),
        ).count()
        
        # 5. Transacciones con comercio desconocido o genérico
        comercios_desconocidos = session.query(Transaction).filter(
            Transaction.profile_id == profile_id,
            Transaction.es_desconocida == True,
            Transaction.deleted_at.is_(None),
        ).count()
        
        # 6. Depósitos/Ingresos sin identificar
        from finanzas_tracker.models.income import Income
        ingresos_sin_confirmar = session.query(Income).filter(
            Income.profile_id == profile_id,
            Income.confirmado == False,
            Income.deleted_at.is_(None),
        ).count()
        
        # 7. Preguntas pendientes de IA
        from finanzas_tracker.models.pending_question import PendingQuestion, QuestionStatus
        
        preguntas_ia = session.query(PendingQuestion).filter(
            PendingQuestion.profile_id == profile_id,
            PendingQuestion.status == QuestionStatus.PENDIENTE,
            PendingQuestion.deleted_at.is_(None),
        ).count()
        
        # Totales por grupo
        transferencias_total = transferencias_confusas + transferencias_sin_categoria
        compras_total = compras_sin_categoria + comercios_ambiguos + comercios_desconocidos
        
        total = transferencias_total + compras_total + ingresos_sin_confirmar + preguntas_ia
        
        return {
            "transferencias_confusas": transferencias_confusas,
            "comercios_ambiguos": comercios_ambiguos,
            "compras_sin_categoria": compras_sin_categoria,
            "transferencias_sin_categoria": transferencias_sin_categoria,
            "comercios_desconocidos": comercios_desconocidos,
            "ingresos_sin_confirmar": ingresos_sin_confirmar,
            "preguntas_ia": preguntas_ia,
            # Agrupados
            "transferencias": transferencias_total,
            "compras": compras_total,
            "ingresos": ingresos_sin_confirmar,
            "total": total,
        }


def mostrar_revision_inicial(perfil: Profile) -> bool:
    """
    Muestra la pantalla de revisión inicial después del sync.
    Permite al usuario revisar y clarificar transacciones antes del dashboard.
    
    Returns:
        True si se completó la revisión, False si aún hay pendientes
    """
    pendientes = contar_items_pendientes_revision(str(perfil.id))
    
    # Si no hay nada pendiente, ya terminó
    if pendientes["total"] == 0:
        return True
    
    ocultar_sidebar()
    
    st.markdown(
        """
        <div style='text-align: center; padding: 1rem 0;'>
            <h1 style='font-size: 2.5rem; margin-bottom: 0.5rem;'>🔍 Revisión Inicial</h1>
            <p style='font-size: 1.1rem; color: #666;'>
                Antes de ver tu dashboard, ayúdanos a clarificar algunas transacciones
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    # Mostrar resumen de pendientes - 3 grupos principales
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "🔄 Transferencias", 
            pendientes["transferencias"],
            help="SINPE y transferencias con descripciones confusas"
        )
    with col2:
        st.metric(
            "🛒 Compras/Gastos", 
            pendientes["compras"],
            help="Compras de tarjeta sin categoría o comercios ambiguos"
        )
    with col3:
        st.metric(
            "💰 Ingresos", 
            pendientes["ingresos"],
            help="Depósitos y salarios sin confirmar"
        )
    
    st.divider()
    
    # Tabs para cada tipo de revisión
    tabs = st.tabs([
        f"🔄 Transferencias ({pendientes['transferencias']})",
        f"🛒 Compras ({pendientes['compras']})", 
        f"💰 Ingresos ({pendientes['ingresos']})",
    ])
    
    with tabs[0]:
        _mostrar_revision_transferencias(perfil, pendientes)
    
    with tabs[1]:
        _mostrar_revision_compras(perfil, pendientes)
    
    with tabs[2]:
        _mostrar_revision_ingresos(perfil, pendientes)
    
    st.divider()
    
    # Botón para continuar aunque haya pendientes
    col_left, col_center, col_right = st.columns([1, 2, 1])
    with col_center:
        if st.button("✅ Continuar al Dashboard", use_container_width=True, type="primary"):
            st.session_state["revision_completada"] = True
            st.rerun()
        
        if pendientes["total"] > 0:
            st.caption(f"💡 Puedes revisar los {pendientes['total']} pendientes después en Configuración")
    
    return False


def _mostrar_revision_transferencias(perfil: Profile, pendientes: dict) -> None:
    """Muestra transferencias (SINPE y otras) que necesitan revisión con chatbox AI."""
    from finanzas_tracker.services.transaction_clarifier import TransactionClarifierService
    from finanzas_tracker.services.pattern_learning_service import PatternLearningService
    
    with get_session() as session:
        # Buscar todas las transferencias que necesitan revisión
        transferencias = session.query(Transaction).filter(
            Transaction.profile_id == perfil.id,
            Transaction.deleted_at.is_(None),
            Transaction.necesita_reconciliacion_sinpe == True,
        ).order_by(Transaction.fecha_transaccion.desc()).limit(20).all()
        
        if not transferencias:
            st.success("✅ No hay transferencias pendientes de revisión")
            return
        
        st.markdown("""
        <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    padding: 15px; border-radius: 10px; margin-bottom: 20px;'>
            <p style='color: white; margin: 0; font-size: 1.1rem;'>
                🤖 <strong>Cuéntame de qué fueron estas transferencias.</strong><br>
                <small>Escríbelo como si hablaras conmigo, yo me encargo del resto.</small>
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        # Inicializar servicios
        clarifier = TransactionClarifierService(session)
        learning_service = PatternLearningService(session)
        
        for txn in transferencias:
            # Determinar qué información tenemos
            tiene_beneficiario = bool(txn.beneficiario)
            tiene_concepto = bool(txn.concepto_transferencia)
            
            # Buscar sugerencias de patrones aprendidos
            sugerencias = learning_service.buscar_sugerencias(txn)
            tiene_sugerencia = len(sugerencias) > 0 and sugerencias[0].confidence >= 0.70
            
            # Crear título descriptivo
            if tiene_beneficiario:
                titulo = f"₡{txn.monto_crc:,.0f} → {txn.beneficiario}"
            else:
                titulo = f"₡{txn.monto_crc:,.0f} → Desconocido"
            
            # Badge según estado
            if tiene_sugerencia:
                badge = "💡"  # Tiene sugerencia de patrón aprendido
            elif tiene_beneficiario and tiene_concepto:
                badge = "🔍"  # Tiene datos pero concepto no claro
            elif tiene_beneficiario:
                badge = "❓"  # Tiene beneficiario pero sin concepto
            else:
                badge = "⚠️"  # Sin datos
            
            with st.expander(
                f"{badge} {titulo} ({txn.fecha_transaccion.strftime('%d/%m')})",
                expanded=False,
            ):
                # ===== MOSTRAR SUGERENCIA SI EXISTE =====
                if tiene_sugerencia:
                    mejor_sug = sugerencias[0]
                    st.markdown(f"""
                    <div style='background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); 
                                padding: 12px; border-radius: 8px; margin-bottom: 15px;'>
                        <p style='color: white; margin: 0; font-size: 1rem;'>
                            💡 <strong>Sugerencia:</strong> {mejor_sug.subcategory_name}<br>
                            <small style='opacity: 0.9;'>{mejor_sug.reason} (Confianza: {mejor_sug.confidence:.0%})</small>
                        </p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    col_accept, col_reject = st.columns(2)
                    with col_accept:
                        if st.button("✅ Sí, así es", key=f"accept_sug_{txn.id}", type="primary", use_container_width=True):
                            txn.subcategory_id = mejor_sug.subcategory_id
                            txn.necesita_reconciliacion_sinpe = False
                            txn.notas = f"✅ Aceptado por usuario: {mejor_sug.reason}"
                            session.commit()
                            st.success("✅ ¡Guardado!")
                            time.sleep(0.5)
                            st.rerun()
                    with col_reject:
                        if st.button("❌ No, es otra cosa", key=f"reject_sug_{txn.id}", use_container_width=True):
                            st.session_state[f"show_manual_{txn.id}"] = True
                    
                    # Si rechazó, mostrar opciones manuales
                    if st.session_state.get(f"show_manual_{txn.id}", False):
                        st.divider()
                
                # Mostrar información que tenemos
                col1, col2 = st.columns(2)
                with col1:
                    if tiene_beneficiario:
                        st.success(f"✅ **{txn.beneficiario}**")
                    else:
                        st.warning("⚠️ Beneficiario desconocido")
                    st.caption(f"Monto: ₡{txn.monto_crc:,.2f}")
                
                with col2:
                    if tiene_concepto:
                        concepto_display = txn.concepto_transferencia.replace("_", " ")
                        st.info(f"📝 {concepto_display}")
                    else:
                        st.warning("⚠️ Sin concepto")
                    st.caption(f"Fecha: {txn.fecha_transaccion.strftime('%d/%m/%Y')}")
                
                st.divider()
                
                # ===== CHATBOX CON CLAUDE =====
                st.markdown("##### 💬 Cuéntame de qué fue")
                
                # Key única para el estado de chat de esta transacción
                chat_key = f"chat_txn_{txn.id}"
                response_key = f"response_txn_{txn.id}"
                
                # Input para el usuario
                user_input = st.text_input(
                    "Escribe aquí",
                    key=f"input_{txn.id}",
                    placeholder="Ej: Le pagué al zapatero, Es el alquiler, Fue una cena con amigos...",
                    label_visibility="collapsed",
                )
                
                col_enviar, col_manual = st.columns([1, 1])
                
                with col_enviar:
                    if st.button("🤖 Preguntar a Claude", key=f"ask_{txn.id}", use_container_width=True):
                        if user_input:
                            with st.spinner("🤔 Analizando..."):
                                result = clarifier.clarify_transaction(txn, user_input)
                                st.session_state[response_key] = result
                        else:
                            st.warning("Escribe algo primero")
                
                # Mostrar respuesta de Claude si existe
                if response_key in st.session_state:
                    result = st.session_state[response_key]
                    
                    st.markdown("---")
                    st.markdown(f"**🤖 Claude dice:** {result.respuesta_usuario}")
                    
                    if result.confianza > 0.5:
                        # Mostrar lo que entendió
                        cols = st.columns(3)
                        with cols[0]:
                            st.metric("Descripción", result.descripcion or "-")
                        with cols[1]:
                            st.metric("Beneficiario", result.beneficiario or "-")
                        with cols[2]:
                            st.metric("Categoría", result.categoria_sugerida or "-")
                        
                        if st.button("✅ Sí, guardar así", key=f"confirm_{txn.id}", type="primary"):
                            clarifier.apply_clarification(txn, result)
                            del st.session_state[response_key]
                            st.success("✅ ¡Guardado!")
                            time.sleep(0.5)
                            st.rerun()
                        
                        if st.button("🔄 No, dejar escribir manualmente", key=f"retry_{txn.id}"):
                            del st.session_state[response_key]
                            st.rerun()
                    else:
                        st.info("💡 No estoy muy seguro. Mejor llénalo manualmente:")
                
                with col_manual:
                    with st.popover("✏️ Modo manual", use_container_width=True):
                        # Cargar subcategorías
                        subcategorias = session.query(Subcategory).all()
                        subcat_options = {"-- Sin categoría --": None}
                        subcat_options.update({s.nombre: s.id for s in subcategorias})
                        
                        if not tiene_beneficiario:
                            nuevo_beneficiario = st.text_input(
                                "¿A quién?",
                                key=f"manual_benef_{txn.id}",
                                placeholder="Juan, Electricista..."
                            )
                        else:
                            nuevo_beneficiario = None
                        
                        descripcion = st.text_input(
                            "¿Para qué?",
                            key=f"manual_desc_{txn.id}",
                            placeholder="Alquiler, Arreglo zapatos..."
                        )
                        
                        seleccion = st.selectbox(
                            "Categoría",
                            options=list(subcat_options.keys()),
                            key=f"manual_cat_{txn.id}",
                        )
                        
                        if st.button("💾 Guardar", key=f"manual_save_{txn.id}", type="primary"):
                            if nuevo_beneficiario:
                                txn.beneficiario = nuevo_beneficiario
                                txn.comercio = f"SINPE a {nuevo_beneficiario}"
                            
                            if descripcion:
                                txn.concepto_transferencia = descripcion
                            
                            txn.necesita_reconciliacion_sinpe = False
                            
                            if seleccion != "-- Sin categoría --":
                                txn.subcategory_id = subcat_options[seleccion]
                            
                            session.commit()
                            if response_key in st.session_state:
                                del st.session_state[response_key]
                            st.success("✅ ¡Guardado!")
                            time.sleep(0.5)
                            st.rerun()


def _mostrar_revision_compras(perfil: Profile, pendientes: dict) -> None:
    """Muestra compras/gastos de tarjeta que necesitan revisión."""
    with get_session() as session:
        # Buscar compras confusas
        compras = session.query(Transaction).filter(
            Transaction.profile_id == perfil.id,
            Transaction.tipo_transaccion == "PURCHASE",
            Transaction.deleted_at.is_(None),
            (
                (Transaction.subcategory_id.is_(None)) |
                (Transaction.es_comercio_ambiguo == True) |
                (Transaction.es_desconocida == True)
            )
        ).order_by(Transaction.monto_crc.desc()).limit(15).all()
        
        if not compras:
            st.success("✅ No hay compras pendientes de revisión")
            return
        
        st.info("💡 Estas compras necesitan categoría. ¿En qué gastaste?")
        
        # Cargar subcategorías
        subcategorias = session.query(Subcategory).all()
        subcat_options = {s.nombre: s.id for s in subcategorias}
        
        for txn in compras:
            # Detectar el tipo de problema
            if txn.es_comercio_ambiguo:
                tipo_badge = "❓ Ambiguo"
            elif txn.es_desconocida:
                tipo_badge = "🤷 Desconocido"
            else:
                tipo_badge = "📂 Sin categoría"
            
            with st.expander(
                f"{tipo_badge} ₡{txn.monto_crc:,.0f} - {txn.comercio or 'Sin nombre'} ({txn.fecha_transaccion.strftime('%d/%m')})",
                expanded=False,
            ):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Comercio:** {txn.comercio or 'No especificado'}")
                    st.write(f"**Tipo:** Compra de tarjeta")
                with col2:
                    st.write(f"**Fecha:** {txn.fecha_transaccion.strftime('%d/%m/%Y')}")
                    if txn.ciudad:
                        st.write(f"**Lugar:** {txn.ciudad}")
                
                # Mostrar opciones si es comercio ambiguo
                if txn.es_comercio_ambiguo and txn.categorias_opciones:
                    st.write("**Opciones sugeridas:**", ", ".join(txn.categorias_opciones))
                
                st.divider()
                
                col_nombre, col_cat = st.columns(2)
                
                with col_nombre:
                    nuevo_nombre = st.text_input(
                        "Nombre del comercio",
                        value=txn.comercio or "",
                        key=f"compra_nombre_{txn.id}",
                        placeholder="Ej: Walmart, Farmacia, etc."
                    )
                
                with col_cat:
                    seleccion = st.selectbox(
                        "Categoría",
                        options=["-- Seleccionar --"] + list(subcat_options.keys()),
                        key=f"compra_cat_{txn.id}",
                    )
                
                if st.button("💾 Guardar", key=f"compra_save_{txn.id}"):
                    if nuevo_nombre:
                        txn.comercio = nuevo_nombre
                    if seleccion != "-- Seleccionar --":
                        txn.subcategory_id = subcat_options[seleccion]
                        txn.es_comercio_ambiguo = False
                        txn.es_desconocida = False
                        txn.categoria_confirmada_usuario = True
                        session.commit()
                        st.success("✅ ¡Guardado!")
                        st.rerun()
                    else:
                        st.warning("Selecciona una categoría")


def _mostrar_revision_ingresos(perfil: Profile, pendientes: dict) -> None:
    """Muestra ingresos/depósitos que necesitan confirmación."""
    with get_session() as session:
        from finanzas_tracker.models.income import Income
        
        # Buscar ingresos sin confirmar
        ingresos = session.query(Income).filter(
            Income.profile_id == perfil.id,
            Income.confirmado == False,
            Income.deleted_at.is_(None),
        ).order_by(Income.monto_crc.desc()).limit(15).all()
        
        if not ingresos:
            st.success("✅ No hay ingresos pendientes de revisión")
            return
        
        st.info("💡 Confirma estos ingresos para que aparezcan correctamente en tus reportes.")
        
        tipos_ingreso = ["Salario", "Freelance", "Inversiones", "Reembolso", "Regalo", "Otro"]
        
        for ing in ingresos:
            with st.expander(
                f"💰 ₡{ing.monto_crc:,.0f} - {ing.descripcion or 'Depósito'} ({ing.fecha.strftime('%d/%m')})",
                expanded=False,
            ):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Descripción:** {ing.descripcion or 'Sin descripción'}")
                    st.write(f"**Tipo actual:** {ing.tipo or 'No especificado'}")
                with col2:
                    st.write(f"**Fecha:** {ing.fecha.strftime('%d/%m/%Y')}")
                    st.write(f"**Monto:** ₡{ing.monto_crc:,.0f}")
                
                st.divider()
                
                col_desc, col_tipo = st.columns(2)
                
                with col_desc:
                    nueva_desc = st.text_input(
                        "Descripción",
                        value=ing.descripcion or "",
                        key=f"ingreso_desc_{ing.id}",
                        placeholder="Ej: Salario Diciembre, Pago freelance..."
                    )
                
                with col_tipo:
                    tipo_sel = st.selectbox(
                        "Tipo de ingreso",
                        options=tipos_ingreso,
                        index=tipos_ingreso.index(ing.tipo) if ing.tipo in tipos_ingreso else 0,
                        key=f"ingreso_tipo_{ing.id}",
                    )
                
                es_recurrente = st.checkbox(
                    "Es un ingreso recurrente (ej: salario mensual)",
                    value=ing.es_recurrente or False,
                    key=f"ingreso_rec_{ing.id}",
                )
                
                if st.button("✅ Confirmar Ingreso", key=f"ingreso_save_{ing.id}"):
                    if nueva_desc:
                        ing.descripcion = nueva_desc
                    ing.tipo = tipo_sel
                    ing.es_recurrente = es_recurrente
                    ing.confirmado = True
                    session.commit()
                    st.success("✅ ¡Ingreso confirmado!")
                    st.rerun()
    with col3:
        st.metric("📂 Sin Categoría", pendientes["sin_categoria"])
    with col4:
        st.metric("💬 Preguntas IA", pendientes["preguntas"])
    
    st.divider()
    
    # Tabs para cada tipo de revisión
    tabs = st.tabs([
        f"🔄 SINPE ({pendientes['sinpe']})",
        f"❓ Ambiguos ({pendientes['ambiguos']})", 
        f"📂 Categorizar ({pendientes['sin_categoria']})",
    ])
    
    with tabs[0]:
        _mostrar_revision_sinpe(perfil)
    
    with tabs[1]:
        _mostrar_revision_ambiguos(perfil)
    
    with tabs[2]:
        _mostrar_revision_categorias(perfil)
    
    st.divider()
    
    # Botón para continuar aunque haya pendientes
    col_left, col_center, col_right = st.columns([1, 2, 1])
    with col_center:
        if st.button("✅ Continuar al Dashboard", use_container_width=True, type="primary"):
            st.session_state["revision_completada"] = True
            st.rerun()
        
        if pendientes["total"] > 0:
            st.caption(f"💡 Puedes revisar los {pendientes['total']} pendientes después en Configuración")
    
    return False


def mostrar_onboarding_nuevo_usuario(perfil: Profile) -> None:
    """
    Muestra el wizard de onboarding para usuarios nuevos.
    Detecta automáticamente el tipo de email y pide permisos.
    """
    ocultar_sidebar()
    
    # Detectar proveedor de email
    email_provider = st.session_state.get("email_provider") or _detectar_proveedor_email(perfil.email_outlook or "")
    
    st.markdown(
        f"""
        <div style='text-align: center; padding: 2rem 0 1rem 0;'>
            <h1 style='font-size: 3rem; margin-bottom: 0;'>🎉</h1>
            <h1 style='font-size: 2rem; margin-bottom: 0.5rem; color: #1f1f1f;'>
                ¡Bienvenido, {perfil.nombre}!
            </h1>
            <p style='font-size: 1.1rem; color: #666;'>
                Vamos a importar tus transacciones
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Flujo según el tipo de email
    if email_provider == "outlook":
        _onboarding_outlook(perfil)
    elif email_provider == "gmail":
        _onboarding_gmail(perfil)
    else:
        _onboarding_pdf(perfil)


def _onboarding_outlook(perfil: Profile) -> None:
    """Onboarding para usuarios con email de Outlook/Hotmail."""
    st.markdown(
        """
        <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    padding: 2rem; border-radius: 16px; text-align: center; color: white; margin-bottom: 1.5rem;'>
            <h2 style='margin: 0 0 0.5rem 0; font-size: 2rem;'>📧</h2>
            <h3 style='margin: 0 0 0.5rem 0; color: white;'>Detectamos que usas Outlook</h3>
            <p style='margin: 0; opacity: 0.9;'>
                Podemos buscar automáticamente tus estados de cuenta bancarios
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🔗 Conectar mi Outlook", type="primary", use_container_width=True, key="btn_connect_outlook"):
            _conectar_outlook(perfil)
    
    _mostrar_opcion_saltar(perfil)


def _onboarding_gmail(perfil: Profile) -> None:
    """Onboarding para usuarios con email de Gmail."""
    st.markdown(
        """
        <div style='background: linear-gradient(135deg, #EA4335 0%, #FBBC05 100%); 
                    padding: 2rem; border-radius: 16px; text-align: center; color: white; margin-bottom: 1.5rem;'>
            <h2 style='margin: 0 0 0.5rem 0; font-size: 2rem;'>📨</h2>
            <h3 style='margin: 0 0 0.5rem 0; color: white;'>Detectamos que usas Gmail</h3>
            <p style='margin: 0; opacity: 0.9;'>
                Podemos buscar automáticamente tus estados de cuenta bancarios
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🔗 Conectar mi Gmail", type="primary", use_container_width=True, key="btn_connect_gmail"):
            _conectar_gmail(perfil)
    
    _mostrar_opcion_saltar(perfil)


def _onboarding_pdf(perfil: Profile) -> None:
    """Onboarding para usuarios con otros emails (Yahoo, iCloud, etc.)."""
    st.markdown(
        """
        <div style='background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); 
                    padding: 2rem; border-radius: 16px; text-align: center; color: white; margin-bottom: 1.5rem;'>
            <h2 style='margin: 0 0 0.5rem 0; font-size: 2rem;'>📄</h2>
            <h3 style='margin: 0 0 0.5rem 0; color: white;'>Sube tu estado de cuenta</h3>
            <p style='margin: 0; opacity: 0.9;'>
                Sube el PDF de tu estado de cuenta de BAC o Banco Popular
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("📤 Subir Estado de Cuenta", type="primary", use_container_width=True, key="btn_upload_pdf"):
            st.switch_page("pages/00_onboarding.py")
    
    _mostrar_opcion_saltar(perfil)


def _mostrar_opcion_saltar(perfil: Profile) -> None:
    """Muestra la opción de saltar el onboarding."""
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: #888; margin-top: 1rem;'>
            <p>¿Prefieres agregar transacciones manualmente después?</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("Saltar por ahora →", use_container_width=True, key="btn_skip_onboarding"):
            _crear_tarjeta_placeholder(perfil)
            st.rerun()


def _marcar_onboarding_completado(perfil: Profile) -> int:
    """
    Marca el onboarding como completado en la BD.
    También crea una tarjeta placeholder y genera preguntas SINPE.
    
    Returns:
        Número de preguntas SINPE creadas
    """
    preguntas_creadas = 0
    
    with get_session() as session:
        # Marcar onboarding como completado
        perfil_db = session.query(Profile).filter(Profile.id == perfil.id).first()
        if perfil_db:
            perfil_db.onboarding_completado = True
            perfil_db.onboarding_step = "completed"
            logger.info(f"✅ Onboarding completado para {perfil_db.nombre}")
        
        # Crear tarjeta placeholder (backwards compatibility)
        from finanzas_tracker.models.card import Card
        existe_tarjeta = session.query(Card).filter(
            Card.profile_id == perfil.id,
            Card.deleted_at.is_(None),
        ).first()
        
        if not existe_tarjeta:
            placeholder_card = Card(
                profile_id=perfil.id,
                ultimos_4_digitos="0000",
                tipo="debito",
                banco="otro",
                alias="Tarjeta Principal",
                activa=True,
            )
            session.add(placeholder_card)
        
        session.commit()
        
        # ================================================================
        # RECONCILIACIÓN AUTOMÁTICA CON CORREOS
        # ================================================================
        # Primero intentamos hacer match automático entre transacciones
        # del PDF y correos de "Notificación de Transferencia"
        # ================================================================
        from finanzas_tracker.services.sinpe_reconciliation_service import (
            SinpeReconciliationService,
        )
        
        sinpe_service = SinpeReconciliationService(session)
        
        # 1. Reconciliar con correos (match automático)
        # Usar la fecha de corte del PDF si existe
        try:
            # Obtener fecha de corte del perfil (guardada por SyncStrategy)
            perfil_db_for_date = session.query(Profile).filter(Profile.id == perfil.id).first()
            fecha_corte = None
            if perfil_db_for_date and perfil_db_for_date.last_statement_date:
                from datetime import datetime, UTC
                fecha_corte = datetime.combine(
                    perfil_db_for_date.last_statement_date, 
                    datetime.min.time()
                ).replace(tzinfo=UTC)
                logger.info(f"📅 Usando fecha de corte del PDF: {fecha_corte.strftime('%d/%m/%Y')}")
            
            reconciliacion_stats = sinpe_service.reconciliar_con_correos(
                str(perfil.id), 
                fecha_corte=fecha_corte
            )
            logger.info(
                f"🔄 Reconciliación: {reconciliacion_stats.get('matches_exactos', 0)} matches automáticos"
            )
        except Exception as e:
            logger.warning(f"Error en reconciliación automática: {e}")
        
        # 2. Generar preguntas para las que NO tuvieron match
        preguntas = sinpe_service.analizar_transacciones_pendientes(str(perfil.id))
        preguntas_creadas = len(preguntas)
        
        if preguntas_creadas > 0:
            logger.info(f"📝 Creadas {preguntas_creadas} preguntas SINPE para {perfil.nombre}")
    
    return preguntas_creadas


# Alias para backwards compatibility
_crear_tarjeta_placeholder = _marcar_onboarding_completado


def mostrar_onboarding_antiguo(perfil: Profile) -> None:
    """
    Versión antigua del onboarding con las 3 opciones.
    Se mantiene por si se quiere usar después.
    """
    ocultar_sidebar()
    
    st.markdown(
        f"""
        <div style='text-align: center; padding: 2rem 0 1rem 0;'>
            <h1 style='font-size: 3rem; margin-bottom: 0;'>🎉</h1>
            <h1 style='font-size: 2rem; margin-bottom: 0.5rem; color: #1f1f1f;'>
                ¡Bienvenido, {perfil.nombre}!
            </h1>
            <p style='font-size: 1.1rem; color: #666;'>
                Vamos a configurar tu cuenta en 2 minutos
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Paso 1: Elegir método de importación
    st.markdown("### 📥 ¿Cómo quieres importar tus transacciones?")
    st.markdown("*Elige la opción más conveniente para ti*")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown(
            """
            <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                        padding: 1.5rem; border-radius: 16px; text-align: center; color: white; min-height: 140px;'>
                <h2 style='margin: 0 0 0.5rem 0; font-size: 2rem;'>📧</h2>
                <h3 style='margin: 0 0 0.5rem 0; color: white; font-size: 1.1rem;'>Outlook/Hotmail</h3>
                <p style='margin: 0; opacity: 0.9; font-size: 0.8rem;'>
                    Cuentas Microsoft
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔗 Conectar Outlook", type="primary", use_container_width=True, key="btn_outlook"):
            _conectar_outlook(perfil)
    
    with col2:
        st.markdown(
            """
            <div style='background: linear-gradient(135deg, #EA4335 0%, #FBBC05 100%); 
                        padding: 1.5rem; border-radius: 16px; text-align: center; color: white; min-height: 140px;'>
                <h2 style='margin: 0 0 0.5rem 0; font-size: 2rem;'>📨</h2>
                <h3 style='margin: 0 0 0.5rem 0; color: white; font-size: 1.1rem;'>Gmail</h3>
                <p style='margin: 0; opacity: 0.9; font-size: 0.8rem;'>
                    Cuentas Google
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔗 Conectar Gmail", type="primary", use_container_width=True, key="btn_gmail"):
            _conectar_gmail(perfil)
    
    with col3:
        st.markdown(
            """
            <div style='background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); 
                        padding: 1.5rem; border-radius: 16px; text-align: center; color: white; min-height: 140px;'>
                <h2 style='margin: 0 0 0.5rem 0; font-size: 2rem;'>📄</h2>
                <h3 style='margin: 0 0 0.5rem 0; color: white; font-size: 1.1rem;'>Subir PDF</h3>
                <p style='margin: 0; opacity: 0.9; font-size: 0.8rem;'>
                    Estado de cuenta manual
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("📤 Subir PDF", type="secondary", use_container_width=True, key="btn_pdf"):
            st.switch_page("pages/00_onboarding.py")
    
    st.markdown("---")
    
    # Opción alternativa: Empezar vacío
    st.markdown(
        """
        <div style='text-align: center; color: #888; margin-top: 1rem;'>
            <p>¿Prefieres agregar transacciones manualmente?</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("Empezar sin datos →", use_container_width=True, key="btn_skip"):
            # Marcar que ya pasó el onboarding creando una tarjeta dummy
            st.session_state["skip_onboarding"] = True
            st.rerun()
    
    # Si eligió saltar
    if st.session_state.get("skip_onboarding"):
        st.session_state["skip_onboarding"] = False
        st.info("👍 Puedes importar transacciones después desde el menú lateral.")
        time.sleep(1.5)
        # Crear una tarjeta placeholder para que no vuelva al onboarding
        with get_session() as session:
            from finanzas_tracker.models.card import Card
            placeholder_card = Card(
                profile_id=perfil.id,
                ultimos_4_digitos="0000",
                tipo="debito",
                banco="otro",
                alias="Tarjeta Principal",
                activa=True,
            )
            session.add(placeholder_card)
            session.commit()
        st.rerun()


def main() -> None:
    """Función principal del dashboard."""

    # Verificar perfil activo
    perfil_activo = get_active_profile()

    if not perfil_activo:
        # Mostrar pantalla de login/registro (sin sidebar)
        mostrar_pantalla_login()
        return

    # ========================================================================
    # FLUJO DE ESTADOS DEL USUARIO (FAANG Best Practices)
    # ========================================================================
    # 1. Onboarding no completado → Mostrar wizard de onboarding
    # 2. Onboarding completado + items pendientes → Pantalla de revisión
    # 3. Todo listo → Dashboard principal
    # ========================================================================
    
    with get_session() as session:
        # Refrescar perfil desde BD para obtener estado actualizado
        perfil_db = session.query(Profile).filter(
            Profile.id == perfil_activo.id
        ).first()
        
        if not perfil_db:
            st.error("Error: Perfil no encontrado")
            return
        
        # ----------------------------------------------------------------
        # ESTADO 1: Onboarding NO completado
        # → Usuario nuevo o que cerró antes de terminar onboarding
        # ----------------------------------------------------------------
        if not perfil_db.onboarding_completado:
            # Verificar si tiene transacciones (cerró durante sincronización)
            count_transacciones = session.query(Transaction).filter(
                Transaction.profile_id == perfil_activo.id,
                Transaction.deleted_at.is_(None),
            ).count()
            
            if count_transacciones > 0:
                # Tiene datos pero no completó onboarding → Marcar como completado
                perfil_db.onboarding_completado = True
                perfil_db.onboarding_step = "completed_auto"
                session.commit()
                logger.info(f"✅ Onboarding auto-completado para {perfil_db.nombre} ({count_transacciones} txns)")
            else:
                # Realmente es nuevo, mostrar onboarding
                mostrar_onboarding_nuevo_usuario(perfil_activo)
                return
        
        # ----------------------------------------------------------------
        # ESTADO 2: Onboarding completado, verificar items pendientes
        # → Mostrar pantalla de revisión SI hay items que clarificar
        # ----------------------------------------------------------------
        if not st.session_state.get("revision_completada", False):
            pendientes = contar_items_pendientes_revision(str(perfil_activo.id))
            
            # Si hay pendientes significativos (>3), mostrar revisión
            if pendientes["total"] > 3:
                revision_ok = mostrar_revision_inicial(perfil_activo)
                if not revision_ok:
                    return

    # ----------------------------------------------------------------
    # ESTADO 3: Dashboard principal
    # ----------------------------------------------------------------
    
    # Obtener fecha actual
    hoy = date.today()

    # Recolectar datos del mes para sidebar y dashboard
    with get_session() as session:
        # Primero verificamos si hay transacciones en el mes actual
        primer_dia_actual = date(hoy.year, hoy.month, 1)
        if hoy.month == 12:
            proximo_mes_actual = date(hoy.year + 1, 1, 1)
        else:
            proximo_mes_actual = date(hoy.year, hoy.month + 1, 1)

        # Contar transacciones del mes actual
        txns_mes_actual = (
            session.query(Transaction)
            .filter(
                Transaction.profile_id == perfil_activo.id,
                Transaction.fecha_transaccion >= primer_dia_actual,
                Transaction.fecha_transaccion < proximo_mes_actual,
                Transaction.deleted_at.is_(None),
            )
            .count()
        )

        # Si no hay transacciones este mes, buscar el último mes con datos
        if txns_mes_actual == 0:
            from sqlalchemy import func as sql_func
            ultima_fecha = session.query(sql_func.max(Transaction.fecha_transaccion)).filter(
                Transaction.profile_id == perfil_activo.id,
                Transaction.deleted_at.is_(None),
            ).scalar()

            if ultima_fecha:
                # Usar el mes de la última transacción
                mes_mostrar = ultima_fecha.month
                anio_mostrar = ultima_fecha.year
                mostrando_historico = True
            else:
                # No hay transacciones, usar mes actual
                mes_mostrar = hoy.month
                anio_mostrar = hoy.year
                mostrando_historico = False
        else:
            mes_mostrar = hoy.month
            anio_mostrar = hoy.year
            mostrando_historico = False

        # Calcular primer día y próximo mes para el mes a mostrar
        primer_dia = date(anio_mostrar, mes_mostrar, 1)
        if mes_mostrar == 12:
            proximo_mes = date(anio_mostrar + 1, 1, 1)
        else:
            proximo_mes = date(anio_mostrar, mes_mostrar + 1, 1)

        mes_nombre = calendar.month_name[mes_mostrar]

        # PATRIMONIO TOTAL - Solo cuentas (más realista)
        # Saldo en cuentas (ahorros, CDPs, inversiones, efectivo)
        patrimonio_cuentas = Account.calcular_patrimonio_total(session, perfil_activo.id)

        # Total histórico de gastos (solo para referencia)
        total_gastos_historicos = (
            session.query(Transaction)
            .filter(
                Transaction.profile_id == perfil_activo.id,
                Transaction.deleted_at.is_(None),
            )
            .all()
        )
        patrimonio_gastos = sum(g.calcular_monto_patrimonio() for g in total_gastos_historicos)

        # Total histórico de ingresos
        total_ingresos_historicos = (
            session.query(Income)
            .filter(
                Income.profile_id == perfil_activo.id,
                Income.deleted_at.is_(None),
            )
            .all()
        )
        patrimonio_ingresos = sum(i.calcular_monto_patrimonio() for i in total_ingresos_historicos)

        # Para el patrimonio, solo usamos cuentas reales
        # Si no hay cuentas configuradas, mostramos N/A
        patrimonio_total = patrimonio_cuentas if patrimonio_cuentas > 0 else None

        # Intereses proyectados
        intereses_mensuales = Account.calcular_intereses_mensuales_totales(
            session, perfil_activo.id
        )

        # DATOS DEL MES ACTUAL
        ingresos_mes = (
            session.query(Income)
            .filter(
                Income.profile_id == perfil_activo.id,
                Income.fecha >= primer_dia,
                Income.fecha < proximo_mes,
                Income.deleted_at.is_(None),
            )
            .all()
        )
        total_ingresos_mes = sum(i.monto_crc for i in ingresos_mes)

        gastos_mes = (
            session.query(Transaction)
            .options(joinedload(Transaction.subcategory).joinedload(Subcategory.category))
            .filter(
                Transaction.profile_id == perfil_activo.id,
                Transaction.fecha_transaccion >= primer_dia,
                Transaction.fecha_transaccion < proximo_mes,
                Transaction.deleted_at.is_(None),
                Transaction.excluir_de_presupuesto == False,
            )
            .all()
        )
        total_gastos_mes = sum(g.monto_crc for g in gastos_mes)
        balance_mes = total_ingresos_mes - total_gastos_mes

        # Transacciones sin revisar
        sin_revisar = (
            session.query(Transaction)
            .filter(
                Transaction.profile_id == perfil_activo.id,
                Transaction.necesita_revision == True,
                Transaction.deleted_at.is_(None),
            )
            .count()
        )

        # Gastos por día del mes (para gráfico)
        gastos_por_dia: dict[int, float] = defaultdict(float)
        for gasto in gastos_mes:
            dia = gasto.fecha_transaccion.day
            gastos_por_dia[dia] += float(gasto.monto_crc)

        # Gastos por categoría (top 5) - usando subcategory -> category
        gastos_por_categoria: dict[str, float] = defaultdict(float)
        for gasto in gastos_mes:
            if gasto.subcategory and gasto.subcategory.category:
                gastos_por_categoria[gasto.subcategory.category.nombre] += float(gasto.monto_crc)

        # NUEVO: Breakdown 50/30/20 por tipo de categoría
        gastos_por_tipo: dict[str, float] = defaultdict(float)
        gastos_por_subcategoria: dict[str, dict] = {}
        for gasto in gastos_mes:
            if gasto.subcategory and gasto.subcategory.category:
                tipo = gasto.subcategory.category.tipo
                gastos_por_tipo[tipo] += float(gasto.monto_crc)
                
                subcat_nombre = gasto.subcategory.nombre
                if subcat_nombre not in gastos_por_subcategoria:
                    gastos_por_subcategoria[subcat_nombre] = {
                        'tipo': tipo,
                        'icono': gasto.subcategory.icono or '',
                        'monto': 0,
                        'count': 0
                    }
                gastos_por_subcategoria[subcat_nombre]['monto'] += float(gasto.monto_crc)
                gastos_por_subcategoria[subcat_nombre]['count'] += 1

        # ========================================================================
        # ANALYTICS AVANZADO - Datos adicionales
        # ========================================================================

        # 1. Top Merchants (gastos por comercio normalizado o campo comercio)
        gastos_por_merchant: dict[str, float] = defaultdict(float)
        for gasto in gastos_mes:
            if gasto.merchant:
                merchant_name = gasto.merchant.nombre_normalizado
            elif gasto.comercio:
                # Limpiar y normalizar el nombre del comercio
                merchant_name = gasto.comercio.split(',')[0].strip()[:30]  # Primeros 30 chars
            else:
                merchant_name = "Sin identificar"
            gastos_por_merchant[merchant_name] += float(gasto.monto_crc)

        # 2. Breakdown de cuentas por tipo
        cuentas_activas = (
            session.query(Account)
            .filter(
                Account.profile_id == perfil_activo.id,
                Account.activa == True,
                Account.deleted_at.is_(None),
            )
            .all()
        )

        cuentas_por_tipo = defaultdict(float)
        for cuenta in cuentas_activas:
            cuentas_por_tipo[cuenta.tipo] += cuenta.saldo_crc

    # Mostrar sidebar simple (solo perfil)
    mostrar_sidebar_simple(perfil_activo)

    # Header minimalista
    if mostrando_historico:
        periodo_texto = f"📅 {mes_nombre} {anio_mostrar} (último mes con datos)"
    else:
        periodo_texto = f"{mes_nombre} {hoy.year} • Día {hoy.day}"

    st.markdown(
        f"""
        <div style='margin-bottom: 1.5rem;'>
            <p style='margin: 0; color: #6b7280; font-size: 0.95rem; font-weight: 500;'>
                {periodo_texto}
            </p>
            <h1 style='margin: 0.25rem 0 0 0; color: #111827; font-size: 2rem; font-weight: 700;'>
                Hola, {perfil_activo.nombre} 👋
            </h1>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Mostrar mensaje si estamos viendo datos históricos
    if mostrando_historico:
        st.info(
            f"📊 Mostrando datos de **{mes_nombre} {anio_mostrar}** porque no hay transacciones en el mes actual. "
            f"Sincroniza tu correo para obtener nuevas transacciones."
        )

    # Verificar si hay transacciones tentativas o preguntas pendientes
    with get_session() as session:
        # Contar transacciones tentativas
        txns_tentativas = (
            session.query(Transaction)
            .filter(
                Transaction.profile_id == perfil_activo.id,
                Transaction.es_tentativa == True,
                Transaction.deleted_at.is_(None),
            )
            .count()
        )
        
        # Contar preguntas pendientes
        preguntas_pendientes = (
            session.query(PendingQuestion)
            .filter(
                PendingQuestion.profile_id == perfil_activo.id,
                PendingQuestion.status == QuestionStatus.PENDIENTE,
            )
            .count()
        )
    
    # Mostrar alertas si hay datos tentativos o preguntas
    if txns_tentativas > 0:
        st.warning(
            f"⚠️ **{txns_tentativas} transacciones tentativas** - Importadas sin estado de cuenta base. "
            "Los saldos pueden variar cuando llegue tu próximo estado de cuenta."
        )
    
    if preguntas_pendientes > 0:
        st.info(
            f"❓ **{preguntas_pendientes} preguntas pendientes** sobre tus transacciones. "
            "[Respóndelas aquí →](/Preguntas)"
        )

    # HERO METRIC - Gastos del Período o Patrimonio
    if patrimonio_total is not None:
        # Si hay patrimonio en cuentas, mostrarlo
        cambio_mes = balance_mes
        cambio_text = f"+₡{cambio_mes:,.0f}" if cambio_mes >= 0 else f"₡{cambio_mes:,.0f}"
        metric_title = "Patrimonio Total"
        metric_value = f"₡{patrimonio_total:,.0f}"
        metric_subtitle = f"{cambio_text} este mes"
    else:
        # Si no hay cuentas, mostrar gastos del período
        metric_title = f"Gastos de {mes_nombre}"
        metric_value = f"₡{total_gastos_mes:,.0f}"
        metric_subtitle = f"{len(gastos_mes)} transacciones"

    st.markdown(
        f"""
        <div class="hero-metric">
            <p style='margin: 0 0 0.5rem 0; font-size: 0.9rem; text-transform: uppercase;
                      letter-spacing: 1px; opacity: 0.9;'>
                {metric_title}
            </p>
            <h1>{metric_value}</h1>
            <p>{metric_subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # PROYECCIONES DE INTERESES (si hay cuentas con interés)
    if intereses_mensuales > 0:
        st.markdown("### 💰 Proyección de Ganancias por Intereses")
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                label="Este Mes",
                value=f"₡{intereses_mensuales:,.0f}",
                delta="Intereses ganados",
                delta_color="normal",
            )

        with col2:
            intereses_3meses = intereses_mensuales * 3
            st.metric(
                label="3 Meses",
                value=f"₡{intereses_3meses:,.0f}",
                delta=f"₡{intereses_mensuales:,.0f}/mes",
            )

        with col3:
            intereses_6meses = intereses_mensuales * 6
            st.metric(
                label="6 Meses",
                value=f"₡{intereses_6meses:,.0f}",
                delta=f"₡{intereses_mensuales:,.0f}/mes",
            )

        with col4:
            intereses_anuales = intereses_mensuales * 12
            st.metric(
                label="1 Año",
                value=f"₡{intereses_anuales:,.0f}",
                delta=f"₡{intereses_mensuales:,.0f}/mes",
            )

        st.markdown("---")

    # MÉTRICAS DEL MES - Grid de 4 columnas
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="💵 Ingresos",
            value=f"₡{total_ingresos_mes:,.0f}",
            delta=f"{len(ingresos_mes)} ingresos" if len(ingresos_mes) > 0 else "Sin ingresos",
        )

    with col2:
        st.metric(
            label="💸 Gastos",
            value=f"₡{total_gastos_mes:,.0f}",
            delta=f"{len(gastos_mes)} transacciones" if len(gastos_mes) > 0 else "Sin gastos",
            delta_color="inverse" if total_gastos_mes > 0 else "off",
        )

    with col3:
        porcentaje_ahorro = (
            (float(balance_mes) / float(total_ingresos_mes) * 100) if total_ingresos_mes > 0 else 0.0
        )
        st.metric(
            label="📈 Tasa Ahorro",
            value=f"{porcentaje_ahorro:.1f}%",
            delta="Positivo" if balance_mes >= 0 else "Negativo",
            delta_color="normal" if balance_mes >= 0 else "inverse",
        )

    with col4:
        if sin_revisar > 0:
            st.metric(
                label="⚠️ Sin Revisar",
                value=sin_revisar,
                delta="Requieren revisión",
                delta_color="inverse",
            )
        else:
            st.metric(
                label="✅ Transacciones",
                value="Al día",
                delta="Todo revisado",
                delta_color="normal",
            )

    # Barra de progreso de gastos (visual importante)
    if total_ingresos_mes > 0:
        porcentaje_gastado = (float(total_gastos_mes) / float(total_ingresos_mes)) * 100

        st.markdown("---")
        col1, col2 = st.columns([3, 1])

        with col1:
            st.markdown(f"**Progreso de Gastos: {porcentaje_gastado:.1f}%**")
            st.progress(min(porcentaje_gastado / 100, 1.0))

            # Mensaje contextual
            if porcentaje_gastado > BUDGET_EXCEEDED_THRESHOLD:
                st.caption(f"🚨 Excediste el presupuesto por ₡{abs(balance_mes):,.0f}")
            elif porcentaje_gastado > BUDGET_WARNING_THRESHOLD:
                st.caption(f"⚠️ Cerca del límite - Te quedan ₡{balance_mes:,.0f}")
            elif porcentaje_gastado > BUDGET_CAUTION_THRESHOLD:
                st.caption(f"📊 Buen ritmo - Disponible: ₡{balance_mes:,.0f}")
            else:
                st.caption(f"✅ Excelente control - Ahorro: ₡{balance_mes:,.0f}")

        with col2:
            st.metric(
                "Balance Mes",
                f"₡{balance_mes:,.0f}",
                delta=f"{100 - porcentaje_gastado:.0f}% disponible"
                if balance_mes >= 0
                else "Déficit",
                delta_color="normal" if balance_mes >= 0 else "inverse",
            )

    # GRÁFICOS Y ANÁLISIS
    if total_gastos_mes > 0:
        st.markdown("---")
        
        # ====================================================================
        # INSIGHTS INTELIGENTES - Alertas y predicciones
        # ====================================================================
        with get_session() as session:
            insights_service = InsightsService(session)
            insights = insights_service.generar_insights(str(perfil.id))
        
        if insights:
            st.markdown("### 💡 Insights del Mes")
            
            # Mostrar insights por prioridad
            for insight in insights[:5]:  # Máximo 5 insights
                # Color y estilo según tipo
                if insight.tipo == InsightType.ALERT:
                    bg_color = "#fef2f2"
                    border_color = "#dc2626"
                    text_color = "#991b1b"
                elif insight.tipo == InsightType.WARNING:
                    bg_color = "#fffbeb"
                    border_color = "#d97706"
                    text_color = "#92400e"
                elif insight.tipo == InsightType.SUCCESS:
                    bg_color = "#f0fdf4"
                    border_color = "#16a34a"
                    text_color = "#166534"
                else:
                    bg_color = "#f0f9ff"
                    border_color = "#0284c7"
                    text_color = "#075985"
                
                st.markdown(
                    f"""
                    <div style='background: {bg_color}; 
                                border-radius: 12px; padding: 1rem; 
                                margin-bottom: 0.75rem;
                                border-left: 4px solid {border_color};'>
                        <div style='display: flex; align-items: center; gap: 0.5rem;'>
                            <span style='font-size: 1.5rem;'>{insight.icono}</span>
                            <div>
                                <p style='margin: 0; font-weight: 600; color: {text_color};'>
                                    {insight.titulo}
                                </p>
                                <p style='margin: 0.25rem 0 0 0; color: #4b5563; font-size: 0.9rem;'>
                                    {insight.mensaje}
                                </p>
                            </div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            
            st.markdown("---")
        
        # ====================================================================
        # BREAKDOWN 50/30/20 - Metodología de presupuesto
        # ====================================================================
        st.markdown("### 📊 Análisis 50/30/20")
        st.markdown(
            "<p style='color: #6b7280; margin-bottom: 1rem;'>"
            "Metodología: 50% necesidades, 30% gustos, 20% ahorros</p>",
            unsafe_allow_html=True,
        )
        
        # Calcular totales por tipo
        total_necesidades = gastos_por_tipo.get('necesidades', 0.0)
        total_gustos = gastos_por_tipo.get('gustos', 0.0)
        total_ahorros = gastos_por_tipo.get('ahorros', 0.0)
        
        # Calcular porcentajes (basado en ingresos si hay, o en gastos totales)
        # Convertimos a float para evitar error de tipos con Decimal
        base_calculo = float(total_ingresos_mes if total_ingresos_mes > 0 else total_gastos_mes)
        pct_necesidades = (total_necesidades / base_calculo * 100) if base_calculo > 0 else 0.0
        pct_gustos = (total_gustos / base_calculo * 100) if base_calculo > 0 else 0.0
        pct_ahorros = (total_ahorros / base_calculo * 100) if base_calculo > 0 else 0.0
        
        # Determinar colores según cumplimiento
        def get_color_and_status(pct: float, ideal: float, is_ahorro: bool = False) -> tuple:
            if is_ahorro:
                # Para ahorros, más es mejor
                if pct >= ideal:
                    return "#059669", "✅ Excelente"
                elif pct >= ideal * 0.5:
                    return "#d97706", "⚠️ Bajo"
                else:
                    return "#dc2626", "❌ Muy bajo"
            else:
                # Para gastos, menos es mejor
                if pct <= ideal:
                    return "#059669", "✅ Bien"
                elif pct <= ideal * 1.2:
                    return "#d97706", "⚠️ Cuidado"
                else:
                    return "#dc2626", "❌ Excedido"
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            color, status = get_color_and_status(pct_necesidades, 50)
            st.markdown(
                f"""
                <div style='background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%); 
                            border-radius: 12px; padding: 1.5rem; text-align: center;
                            border-left: 4px solid {color};'>
                    <p style='margin: 0; font-size: 2rem;'>🏠</p>
                    <h3 style='margin: 0.5rem 0; color: #1e3a5f;'>Necesidades</h3>
                    <p style='margin: 0; font-size: 2rem; font-weight: 700; color: {color};'>
                        {pct_necesidades:.1f}%
                    </p>
                    <p style='margin: 0.5rem 0; color: #64748b; font-size: 0.9rem;'>
                        ₡{total_necesidades:,.0f}
                    </p>
                    <p style='margin: 0; font-size: 0.8rem; color: #94a3b8;'>
                        Ideal: 50% • {status}
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            
        with col2:
            color, status = get_color_and_status(pct_gustos, 30)
            st.markdown(
                f"""
                <div style='background: linear-gradient(135deg, #fefce8 0%, #fef3c7 100%); 
                            border-radius: 12px; padding: 1.5rem; text-align: center;
                            border-left: 4px solid {color};'>
                    <p style='margin: 0; font-size: 2rem;'>🎮</p>
                    <h3 style='margin: 0.5rem 0; color: #713f12;'>Gustos</h3>
                    <p style='margin: 0; font-size: 2rem; font-weight: 700; color: {color};'>
                        {pct_gustos:.1f}%
                    </p>
                    <p style='margin: 0.5rem 0; color: #64748b; font-size: 0.9rem;'>
                        ₡{total_gustos:,.0f}
                    </p>
                    <p style='margin: 0; font-size: 0.8rem; color: #94a3b8;'>
                        Ideal: 30% • {status}
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            
        with col3:
            color, status = get_color_and_status(pct_ahorros, 20, is_ahorro=True)
            st.markdown(
                f"""
                <div style='background: linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%); 
                            border-radius: 12px; padding: 1.5rem; text-align: center;
                            border-left: 4px solid {color};'>
                    <p style='margin: 0; font-size: 2rem;'>💎</p>
                    <h3 style='margin: 0.5rem 0; color: #064e3b;'>Ahorros</h3>
                    <p style='margin: 0; font-size: 2rem; font-weight: 700; color: {color};'>
                        {pct_ahorros:.1f}%
                    </p>
                    <p style='margin: 0.5rem 0; color: #64748b; font-size: 0.9rem;'>
                        ₡{total_ahorros:,.0f}
                    </p>
                    <p style='margin: 0; font-size: 0.8rem; color: #94a3b8;'>
                        Ideal: 20% • {status}
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )
        
        # ====================================================================
        # DETALLE POR SUBCATEGORÍA
        # ====================================================================
        if gastos_por_subcategoria:
            st.markdown("---")
            st.markdown("### 💰 Detalle por Subcategoría")
            
            # Ordenar por monto
            subcats_ordenadas = sorted(
                gastos_por_subcategoria.items(),
                key=lambda x: x[1]['monto'],
                reverse=True
            )
            
            # Mostrar en 2 columnas
            col1, col2 = st.columns(2)
            
            for i, (nombre, data) in enumerate(subcats_ordenadas):
                col = col1 if i % 2 == 0 else col2
                pct = (float(data['monto']) / float(total_gastos_mes) * 100) if total_gastos_mes > 0 else 0.0
                
                # Color según tipo
                tipo_color = {
                    'necesidades': '#3b82f6',
                    'gustos': '#f59e0b',
                    'ahorros': '#10b981'
                }.get(data['tipo'], '#6b7280')
                
                with col:
                    st.markdown(
                        f"""
                        <div style='display: flex; justify-content: space-between; 
                                    align-items: center; padding: 0.75rem; 
                                    background: #f8fafc; border-radius: 8px; 
                                    margin-bottom: 0.5rem; border-left: 3px solid {tipo_color};'>
                            <div>
                                <span style='font-size: 1.1rem;'>{data['icono']}</span>
                                <span style='font-weight: 500; margin-left: 0.5rem;'>{nombre}</span>
                                <span style='color: #94a3b8; font-size: 0.8rem; margin-left: 0.5rem;'>
                                    ({data['count']} tx)
                                </span>
                            </div>
                            <div style='text-align: right;'>
                                <span style='font-weight: 600; color: #1f2937;'>₡{data['monto']:,.0f}</span>
                                <span style='color: #6b7280; font-size: 0.8rem; margin-left: 0.5rem;'>
                                    {pct:.1f}%
                                </span>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
        
        st.markdown("---")
        st.markdown("### 📈 Análisis de Gastos")

        # Tres columnas para los gráficos
        col1, col2, col3 = st.columns(3)

        with col1:
            # Gráfico de gastos diarios
            st.markdown("**💸 Gastos Diarios**")
            dias_del_mes = list(range(1, hoy.day + 1))
            montos_por_dia = [gastos_por_dia.get(dia, 0) for dia in dias_del_mes]

            df_dias = pd.DataFrame({"Día": dias_del_mes, "Monto": montos_por_dia})
            st.line_chart(df_dias.set_index("Día"), height=200)

        with col2:
            # Gráfico de gastos acumulados
            st.markdown("**📊 Acumulado del Mes**")
            gastos_acumulados = []
            acumulado = 0
            for dia in dias_del_mes:
                acumulado += gastos_por_dia.get(dia, 0)
                gastos_acumulados.append(acumulado)

            df_acumulado = pd.DataFrame({"Día": dias_del_mes, "Acumulado": gastos_acumulados})
            st.area_chart(df_acumulado.set_index("Día"), height=200)

        with col3:
            # Gráfico de top categorías
            st.markdown("**🏷️ Top Categorías**")
            if gastos_por_categoria:
                top_categorias = sorted(
                    gastos_por_categoria.items(), key=lambda x: x[1], reverse=True
                )[:5]

                df_cats = pd.DataFrame(
                    {
                        "Categoría": [cat[0] for cat in top_categorias],
                        "Monto": [cat[1] for cat in top_categorias],
                    }
                )
                st.bar_chart(df_cats.set_index("Categoría"), height=200)
            else:
                st.info("Sin categorías")

        # ====================================================================
        # ANALYTICS AVANZADO
        # ====================================================================
        st.markdown("---")
        st.markdown("### 📊 Analytics Avanzado")
        st.markdown(
            "<p style='color: #6b7280; margin-bottom: 1.5rem;'>Insights detallados de tus finanzas</p>",
            unsafe_allow_html=True,
        )

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.markdown("**🏪 Top Merchants**")
            if gastos_por_merchant:
                top_merchants = sorted(
                    gastos_por_merchant.items(), key=lambda x: x[1], reverse=True
                )[:5]

                for merchant, monto in top_merchants:
                    porcentaje = (float(monto) / float(total_gastos_mes) * 100) if total_gastos_mes > 0 else 0.0
                    st.markdown(
                        f"<div style='padding: 0.25rem 0;'>"
                        f"<span style='font-size: 0.85rem;'>{merchant}</span><br>"
                        f"<span style='font-weight: 600; color: #dc2626;'>₡{monto:,.0f}</span> "
                        f"<span style='color: #6b7280; font-size: 0.8rem;'>({porcentaje:.1f}%)</span>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
            else:
                st.caption("Sin datos de merchants")

        with col2:
            st.markdown("**💰 Patrimonio Real**")
            if patrimonio_total is not None and patrimonio_total > 0:
                st.metric(
                    "Total",
                    f"₡{patrimonio_total:,.0f}",
                    delta=f"₡{movimientos_netos:,.0f} movimientos",
                    help="Cuentas + Movimientos históricos",
                )

                # Breakdown
                st.caption("**Breakdown:**")
                if patrimonio_cuentas > 0:
                    st.markdown(
                        f"<div style='font-size: 0.85rem;'>"
                        f"🏦 Cuentas: <span style='font-weight: 600;'>₡{patrimonio_cuentas:,.0f}</span><br>"
                        f"📊 Movimientos: <span style='font-weight: 600;'>₡{movimientos_netos:,.0f}</span>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                else:
                    st.caption("Agrega cuentas en Setup")
            else:
                st.metric(
                    "Total",
                    "Sin datos",
                    delta=None,
                    help="Agrega cuentas en Setup para ver tu patrimonio",
                )
                st.caption("💡 Ve a Setup → Cuentas para agregar tus cuentas bancarias")

        with col3:
            st.markdown("**📈 Proyección Intereses**")
            if intereses_mensuales > 0:
                intereses_anuales = intereses_mensuales * 12
                st.metric(
                    "Por Mes",
                    f"₡{intereses_mensuales:,.0f}",
                    delta=f"₡{intereses_anuales:,.0f}/año",
                    help="Intereses generados por tus ahorros y CDPs",
                )

                # Mostrar en cuánto tiempo duplicas tu dinero (regla del 72)
                if patrimonio_cuentas > 0 and intereses_mensuales > 0:
                    tasa_mensual = (intereses_mensuales / patrimonio_cuentas) * 100
                    tasa_anual = tasa_mensual * 12
                    if tasa_anual > 0:
                        anos_duplicar = 72 / tasa_anual
                        st.caption(f"Duplicas tu dinero en ~{anos_duplicar:.1f} años")
            else:
                st.caption("Sin intereses configurados")
                st.caption("Agrega CDPs o savings en Setup")

        with col4:
            st.markdown("**🏦 Breakdown Cuentas**")
            if cuentas_por_tipo:
                # Mostrar tipos de cuenta
                tipo_emoji = {
                    "checking": "💳",
                    "savings": "🏦",
                    "investment": "📈",
                    "cdp": "💰",
                    "cash": "💵",
                }

                for tipo, saldo in sorted(
                    cuentas_por_tipo.items(), key=lambda x: x[1], reverse=True
                ):
                    emoji = tipo_emoji.get(tipo, "💼")
                    porcentaje = (saldo / patrimonio_cuentas * 100) if patrimonio_cuentas > 0 else 0
                    tipo_display = tipo.replace("_", " ").title()

                    st.markdown(
                        f"<div style='padding: 0.25rem 0;'>"
                        f"<span style='font-size: 0.85rem;'>{emoji} {tipo_display}</span><br>"
                        f"<span style='font-weight: 600; color: #059669;'>₡{saldo:,.0f}</span> "
                        f"<span style='color: #6b7280; font-size: 0.8rem;'>({porcentaje:.1f}%)</span>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
            else:
                st.caption("Sin cuentas configuradas")
                st.caption("Agrega cuentas en Setup")

        # Alerta contextual si hay pendientes
        if sin_revisar > 0:
            st.markdown("---")
            st.warning(
                f"⚠️ **Tienes {sin_revisar} transacciones sin revisar.** "
                f"Revísalas para mantener tu presupuesto actualizado."
            )
    else:
        st.info(
            "💡 **Comienza agregando transacciones** para ver análisis detallados "
            "de tus gastos y patrones de consumo."
        )


if __name__ == "__main__":
    main()
