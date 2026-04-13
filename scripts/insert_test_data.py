"""Insert test data for pet_friendly tags and price change indicators.

This script:
1. Sets pet_friendly=True on 2-3 existing listings
2. Inserts price_history records for 2 listings to trigger price change indicators
   - One listing with a price DROP ($200 decrease)
   - One listing with a price INCREASE ($100 increase)
3. Updates first_seen/last_seen so test listings appear on page 1 (sorted newest first)
"""

import sqlite3
from datetime import date, datetime, timedelta, timezone

DB_PATH = "data/listings.db"


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # ---------------------------------------------------------------
    # 1. Fetch some existing listings to work with
    # ---------------------------------------------------------------
    cur.execute(
        "SELECT id, title, price, pet_friendly FROM listings WHERE is_active = 1 LIMIT 5"
    )
    listings = cur.fetchall()

    if len(listings) < 3:
        print(f"ERROR: Need at least 3 active listings, found {len(listings)}")
        conn.close()
        return

    print(f"Found {len(listings)} active listings to work with:\n")
    for row in listings:
        print(f"  id={row['id']}  price=${row['price']:.0f}  pet_friendly={row['pet_friendly']}  title={row['title'][:60]}")

    # ---------------------------------------------------------------
    # 2. Set pet_friendly = 1 on the first 3 listings
    # ---------------------------------------------------------------
    pet_ids = [listings[0]["id"], listings[1]["id"], listings[2]["id"]]
    cur.execute(
        f"UPDATE listings SET pet_friendly = 1 WHERE id IN ({','.join('?' * len(pet_ids))})",
        pet_ids,
    )
    print(f"\n✅ Set pet_friendly=True on listing IDs: {pet_ids}")

    # ---------------------------------------------------------------
    # 2b. Bump first_seen & last_seen so these listings sort to page 1
    #     (dashboard default sort is "Newest First" = first_seen DESC)
    # ---------------------------------------------------------------
    now_ts = datetime.now(timezone.utc).isoformat()
    cur.execute(
        f"UPDATE listings SET first_seen = ?, last_seen = ? "
        f"WHERE id IN ({','.join('?' * len(pet_ids))})",
        [now_ts, now_ts] + pet_ids,
    )
    print(f"✅ Updated first_seen & last_seen to {now_ts} for IDs: {pet_ids}")

    # ---------------------------------------------------------------
    # 3. Insert price_history records for price change indicators
    # ---------------------------------------------------------------
    today = date.today()
    seven_days_ago = today - timedelta(days=7)

    # Listing A: price DROP — was $200 more expensive 7 days ago
    listing_a = listings[0]
    listing_a_id = listing_a["id"]
    listing_a_current_price = listing_a["price"]
    listing_a_old_price = listing_a_current_price + 200  # was higher before

    # Listing B: price INCREASE — was $100 cheaper 7 days ago
    listing_b = listings[1]
    listing_b_id = listing_b["id"]
    listing_b_current_price = listing_b["price"]
    listing_b_old_price = listing_b_current_price - 100  # was lower before

    # Clear any existing price_history for these listings to avoid conflicts
    cur.execute(
        "DELETE FROM price_history WHERE listing_id IN (?, ?)",
        (listing_a_id, listing_b_id),
    )

    # Insert old snapshot (7 days ago) and current snapshot (today)
    price_records = [
        # Listing A: price drop — old price was higher
        (listing_a_id, seven_days_ago.isoformat(), listing_a_old_price),
        (listing_a_id, today.isoformat(), listing_a_current_price),
        # Listing B: price increase — old price was lower
        (listing_b_id, seven_days_ago.isoformat(), listing_b_old_price),
        (listing_b_id, today.isoformat(), listing_b_current_price),
    ]

    cur.executemany(
        "INSERT INTO price_history (listing_id, snapshot_date, price, created_at) "
        "VALUES (?, ?, ?, datetime('now'))",
        price_records,
    )

    print(f"\n✅ Price history for listing ID {listing_a_id} (PRICE DROP 🔻):")
    print(f"   {seven_days_ago} → ${listing_a_old_price:.0f}")
    print(f"   {today}       → ${listing_a_current_price:.0f}")
    print(f"   Change: -$200")

    print(f"\n✅ Price history for listing ID {listing_b_id} (PRICE INCREASE 🔺):")
    print(f"   {seven_days_ago} → ${listing_b_old_price:.0f}")
    print(f"   {today}       → ${listing_b_current_price:.0f}")
    print(f"   Change: +$100")

    conn.commit()

    # ---------------------------------------------------------------
    # 4. Verify the data
    # ---------------------------------------------------------------
    print("\n--- Verification ---")

    cur.execute("SELECT id, title, pet_friendly FROM listings WHERE pet_friendly = 1")
    pet_rows = cur.fetchall()
    print(f"\nPet-friendly listings ({len(pet_rows)}):")
    for row in pet_rows:
        print(f"  id={row['id']}  🐾 pet_friendly={row['pet_friendly']}  title={row['title'][:60]}")

    cur.execute(
        "SELECT listing_id, snapshot_date, price FROM price_history ORDER BY listing_id, snapshot_date"
    )
    ph_rows = cur.fetchall()
    print(f"\nPrice history records ({len(ph_rows)}):")
    for row in ph_rows:
        print(f"  listing_id={row['listing_id']}  date={row['snapshot_date']}  price=${row['price']:.0f}")

    conn.close()
    print("\n✅ Done! Test data inserted successfully.")


if __name__ == "__main__":
    main()
