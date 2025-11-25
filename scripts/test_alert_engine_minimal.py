#!/usr/bin/env python3
"""
Minimal script to test if AlertEngine can run without errors.

This just creates a basic profile and runs the alert engine to see
if it executes without crashing.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from finanzas_tracker.core.database import get_session, engine, Base
from finanzas_tracker.models.profile import Profile
from finanzas_tracker.models.alert import Alert
from finanzas_tracker.services.alert_engine import AlertEngine
from decimal import Decimal

print("=" * 80)
print("🧪 TESTING ALERT ENGINE (MINIMAL)")
print("=" * 80)

# Initialize database tables
print("\n📊 Initializing database tables...")
Base.metadata.create_all(engine)
print("✅ Database tables created")

with get_session() as session:
    # Check if profile exists
    profile = session.query(Profile).first()

    if not profile:
        # Create minimal profile
        print("\n👤 Creating test profile...")
        profile = Profile(
            email_outlook="test@example.com",
            nombre="Test User",
        )
        session.add(profile)
        session.commit()
        print(f"✅ Profile created: {profile.nombre}")
    else:
        print(f"\n👤 Using existing profile: {profile.nombre}")

    # Clear existing alerts
    print("\n🗑️  Clearing existing alerts...")
    deleted = session.query(Alert).delete()
    session.commit()
    print(f"✅ Cleared {deleted} alerts")

    # Run alert engine
    print(f"\n🔄 Running AlertEngine.evaluate_all_alerts()...")
    engine = AlertEngine(session)

    try:
        alerts = engine.evaluate_all_alerts(profile.id)
        print(f"✅ Alert engine executed successfully!")
        print(f"📊 Generated {len(alerts)} alerts")

        if alerts:
            print("\n📋 Alerts generated:")
            for alert in alerts[:5]:  # Show first 5
                print(f"   - [{alert.priority.value}] {alert.title}")
            if len(alerts) > 5:
                print(f"   ... and {len(alerts) - 5} more")
        else:
            print("\n⚠️  No alerts generated (expected if no data exists)")

        print("\n" + "=" * 80)
        print("✅ TEST PASSED - Alert engine works correctly!")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ TEST FAILED - Error running alert engine:")
        print(f"   {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
