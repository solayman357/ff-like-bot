"""Check how many likes a target UID currently has.

Usage: python3 check_likes.py <uid> [region]
"""
import asyncio
import sys
import httpx
import ff_core


def parse_likes(body: bytes):
    """Best-effort parse of GetPlayerPersonalShow protobuf for like count."""
    try:
        fields = ff_core.pb_decode_strings(body)
        # recursively search small strings that look like numbers
        for field, val in fields.items():
            if isinstance(val, bytes):
                try:
                    s = val.decode()
                    if s.isdigit() and 1 < len(s) < 12:
                        return int(s)
                except Exception:
                    pass
        return None
    except Exception:
        return None


async def main():
    if len(sys.argv) < 2:
        print("Usage: python3 check_likes.py <uid> [region]")
        sys.exit(1)
    uid = sys.argv[1]
    region = sys.argv[2].upper() if len(sys.argv) > 2 else "IND"
    async with httpx.AsyncClient() as c:
        r = await ff_core.get_player_info(c, uid, region)
        print(f"HTTP {r.status_code}")
        if r.status_code == 200:
            likes = parse_likes(r.content)
            print(f"Raw bytes: {r.content[:120].hex()}")
            if likes is not None:
                print(f"Likes: {likes}")
            else:
                print("Could not parse like count (may need auth).")


if __name__ == "__main__":
    asyncio.run(main())
