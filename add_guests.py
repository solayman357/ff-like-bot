"""Interactive helper to add guest accounts to guest_accounts.json."""
import json
import os
import sys

GUESTS_FILE = os.path.join(os.path.dirname(__file__), "guest_accounts.json")


def load():
    if os.path.exists(GUESTS_FILE):
        try:
            return json.load(open(GUESTS_FILE))
        except Exception:
            pass
    return []


def main():
    guests = load()
    print(f"Current: {len(guests)} accounts")
    while True:
        uid = input("Guest UID (enter to finish): ").strip()
        if not uid:
            break
        pwd = input("Password: ").strip()
        if not pwd:
            print("Skipped (no password)")
            continue
        guests.append({"uid": uid, "password": pwd})
        print(f"Added {uid}. Total: {len(guests)}")

    with open(GUESTS_FILE, "w") as f:
        json.dump(guests, f, indent=2)
    print(f"Saved {len(guests)} accounts to {GUESTS_FILE}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(0)
