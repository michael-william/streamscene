#!/usr/bin/env python3
"""Quick script to check registered devices in the database."""

from streamscene.core.database import get_db_session
from streamscene.core.models import Device, User, Stream

with get_db_session() as session:
    # Get all devices
    devices = session.query(Device).all()

    print(f"\n{'='*80}")
    print(f"Found {len(devices)} device(s) in database")
    print(f"{'='*80}\n")

    if not devices:
        print("No devices registered yet.\n")
    else:
        for i, device in enumerate(devices, 1):
            print(f"Device #{i}:")
            print(f"  ID: {device.id}")
            print(f"  Device UUID: {device.device_uuid}")
            print(f"  Nickname: {device.nickname}")
            print(f"  User ID: {device.user_id}")

            # Get user info
            if device.user_id:
                user = session.query(User).filter(User.id == device.user_id).first()
                if user:
                    print(f"  Owner: {user.email or user.username or 'Unknown'}")
            else:
                print(f"  Owner: Not registered yet")

            # Get stream info
            if device.current_stream_id:
                stream = session.query(Stream).filter(Stream.id == device.current_stream_id).first()
                if stream:
                    print(f"  Current Stream: {stream.name}")
            else:
                print(f"  Current Stream: None")

            print(f"  Version: {device.current_version}")
            print(f"  Last Seen: {device.last_seen or 'Never'}")
            print(f"  Registered At: {device.registered_at or 'Not registered'}")
            print(f"  Setup State: {device.setup_state}")
            print(f"  API Key Hash: {'Set' if device.api_key_hash else 'Not set'}")
            print()

    # Get all users
    users = session.query(User).all()
    print(f"\n{'='*80}")
    print(f"Found {len(users)} user(s) in database")
    print(f"{'='*80}\n")

    for i, user in enumerate(users, 1):
        print(f"User #{i}:")
        print(f"  ID: {user.id}")
        print(f"  Email: {user.email or 'N/A'}")
        print(f"  Username: {user.username or 'N/A'}")
        print(f"  Authentik ID: {user.authentik_user_id}")
        print()
