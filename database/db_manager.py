# database/db_manager.py
"""SQLite database manager for transport order storage.

3-table schema:
  trucks      — one row per license plate
  week_tables — one row per (truck × week), stores KM/ZALANE/DE km/rate
  orders      — individual transport orders linked to a week table

All computed values (SPALANIE, AUTO DE EUR, SUMA, STAWKA, PO AUT, etc.)
are calculated on-the-fly in Python, never stored in the database.
"""

import sqlite3
import os
from datetime import datetime
from pathlib import Path
from typing import Optional


class DatabaseManager:
    """Manage SQLite database for transport orders.

    Thread-safe via WAL mode and check_same_thread=False.
    Uses parameterised queries throughout.
    """

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def __init__(self, db_path: str = "transport_orders.db") -> None:
        """Open (or create) the database at *db_path*.

        Pass ``':memory:'`` for an in-memory database (useful for tests).
        """
        self.db_path = db_path
        self.conn = sqlite3.connect(
            db_path,
            check_same_thread=False,
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA foreign_keys=ON;")
        self._init_db()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        """Create tables and indexes if they do not exist."""
        with self.conn:
            self.conn.executescript("""
                CREATE TABLE IF NOT EXISTS trucks (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    plate           TEXT UNIQUE NOT NULL,
                    driver_name     TEXT,
                    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS week_tables (
                    id                        INTEGER PRIMARY KEY AUTOINCREMENT,
                    truck_id                  INTEGER NOT NULL REFERENCES trucks(id) ON DELETE CASCADE,
                    week_identifier           TEXT NOT NULL,
                    km_total                  REAL NOT NULL DEFAULT 0,
                    fuel_refueled             REAL DEFAULT 0,
                    km_in_germany             REAL DEFAULT 0,
                    eur_pln_rate              REAL NOT NULL DEFAULT 4.25,
                    extra_highway_charge_eur  REAL DEFAULT 0,
                    created_at                TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(truck_id, week_identifier)
                );

                CREATE TABLE IF NOT EXISTS orders (
                    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                    week_table_id       INTEGER NOT NULL REFERENCES week_tables(id) ON DELETE CASCADE,
                    row_number          INTEGER,
                    zlecenie_nr         TEXT,
                    termin_rozladunku    TEXT,
                    miejsce_zaladunku    TEXT,
                    miejsce_rozladunku   TEXT,
                    fracht_eur          REAL,
                    is_storno           INTEGER DEFAULT 0,
                    full_trip_price     REAL,
                    source_file         TEXT,
                    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(zlecenie_nr, week_table_id)
                );

                CREATE INDEX IF NOT EXISTS idx_orders_week
                    ON orders(week_table_id);
                CREATE INDEX IF NOT EXISTS idx_orders_zlecenie
                    ON orders(zlecenie_nr);
                CREATE INDEX IF NOT EXISTS idx_week_tables_truck
                    ON week_tables(truck_id);
                CREATE INDEX IF NOT EXISTS idx_trucks_plate
                    ON trucks(plate);
            """)

    # ------------------------------------------------------------------
    # Trucks
    # ------------------------------------------------------------------

    def add_truck(self, plate: str, driver_name: Optional[str] = None) -> tuple[int, str]:
        """Insert a truck or return existing one.

        Returns:
            (truck_id, message) — message is 'created' or 'exists'.
        """
        try:
            with self.conn:
                self.conn.execute(
                    "INSERT INTO trucks (plate, driver_name) VALUES (?, ?)",
                    (plate, driver_name),
                )
            truck_id = self.conn.execute(
                "SELECT id FROM trucks WHERE plate = ?", (plate,)
            ).fetchone()["id"]
            return truck_id, "created"
        except sqlite3.IntegrityError:
            row = self.conn.execute(
                "SELECT id FROM trucks WHERE plate = ?", (plate,)
            ).fetchone()
            return row["id"], "exists"

    def get_all_trucks(self) -> list[dict]:
        """Return all trucks sorted by plate."""
        rows = self.conn.execute(
            "SELECT * FROM trucks ORDER BY plate"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_truck_by_plate(self, plate: str) -> Optional[dict]:
        """Return a single truck dict or None."""
        row = self.conn.execute(
            "SELECT * FROM trucks WHERE plate = ?", (plate,)
        ).fetchone()
        return dict(row) if row else None

    def update_truck(self, truck_id: int, driver_name: Optional[str] = None) -> bool:
        """Update driver name for a truck."""
        try:
            with self.conn:
                self.conn.execute(
                    "UPDATE trucks SET driver_name = ? WHERE id = ?",
                    (driver_name, truck_id),
                )
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Week Tables
    # ------------------------------------------------------------------

    def add_week_table(
        self,
        truck_id: int,
        week_identifier: str,
        km_total: float = 0,
        fuel_refueled: float = 0,
        km_in_germany: float = 0,
        eur_pln_rate: float = 4.25,
        extra_highway_charge_eur: float = 0,
    ) -> int:
        """Insert a week table or return existing ID.

        Returns the week_table id.
        """
        try:
            with self.conn:
                self.conn.execute(
                    """INSERT INTO week_tables
                       (truck_id, week_identifier, km_total, fuel_refueled,
                        km_in_germany, eur_pln_rate, extra_highway_charge_eur)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (truck_id, week_identifier, km_total, fuel_refueled,
                     km_in_germany, eur_pln_rate, extra_highway_charge_eur),
                )
            row = self.conn.execute(
                """SELECT id FROM week_tables
                   WHERE truck_id = ? AND week_identifier = ?""",
                (truck_id, week_identifier),
            ).fetchone()
            return row["id"]
        except sqlite3.IntegrityError:
            row = self.conn.execute(
                """SELECT id FROM week_tables
                   WHERE truck_id = ? AND week_identifier = ?""",
                (truck_id, week_identifier),
            ).fetchone()
            return row["id"]

    def get_week_tables(self, truck_id: int) -> list[dict]:
        """Return all week tables for a truck, sorted by identifier."""
        rows = self.conn.execute(
            """SELECT * FROM week_tables
               WHERE truck_id = ?
               ORDER BY week_identifier""",
            (truck_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_week_table(self, week_table_id: int) -> Optional[dict]:
        """Return a single week table dict or None."""
        row = self.conn.execute(
            "SELECT * FROM week_tables WHERE id = ?", (week_table_id,)
        ).fetchone()
        return dict(row) if row else None

    def update_week_table(self, week_table_id: int, **kwargs) -> bool:
        """Update week-table fields.

        Accepted kwargs: km_total, fuel_refueled, km_in_germany,
                         eur_pln_rate, extra_highway_charge_eur, week_identifier.
        """
        allowed = {
            "km_total", "fuel_refueled", "km_in_germany",
            "eur_pln_rate", "extra_highway_charge_eur", "week_identifier",
        }
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return False
        set_clause = ", ".join(f"{col} = ?" for col in updates)
        values = list(updates.values()) + [week_table_id]
        try:
            with self.conn:
                self.conn.execute(
                    f"UPDATE week_tables SET {set_clause} WHERE id = ?",
                    values,
                )
            return True
        except Exception:
            return False

    def delete_week_table(self, week_table_id: int) -> bool:
        """Delete a week table and all its orders (CASCADE)."""
        try:
            with self.conn:
                self.conn.execute(
                    "DELETE FROM week_tables WHERE id = ?", (week_table_id,)
                )
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Orders
    # ------------------------------------------------------------------

    def add_order(
        self,
        week_table_id: int,
        order_data: dict,
    ) -> tuple[bool, str]:
        """Insert a single order into a week table.

        Returns:
            (True, 'inserted')   — success
            (False, 'duplicate') — zlecenie_nr already exists in this week
            (False, error_msg)   — other failure
        """
        zlecenie_nr = order_data.get("zlecenie_nr")
        if zlecenie_nr and self.order_exists(zlecenie_nr, week_table_id):
            return False, "duplicate"

        # Determine fracht / storno
        fracht_raw = order_data.get("fracht_eur", order_data.get("fracht"))
        is_storno = 0
        fracht_eur = None
        if fracht_raw is None or (isinstance(fracht_raw, str) and "storno" in fracht_raw.lower()):
            is_storno = 1
            fracht_eur = None
        else:
            try:
                fracht_eur = float(fracht_raw)
            except (TypeError, ValueError):
                fracht_eur = None
                is_storno = 1

        # Next row number
        row = self.conn.execute(
            "SELECT COALESCE(MAX(row_number), 0) + 1 AS next_row FROM orders WHERE week_table_id = ?",
            (week_table_id,),
        ).fetchone()
        next_row = row["next_row"] if row else 1

        try:
            with self.conn:
                self.conn.execute(
                    """INSERT INTO orders
                       (week_table_id, row_number, zlecenie_nr, termin_rozladunku,
                        miejsce_zaladunku, miejsce_rozladunku, fracht_eur,
                        is_storno, full_trip_price, source_file)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        week_table_id,
                        next_row,
                        zlecenie_nr,
                        order_data.get("termin_rozladunku"),
                        order_data.get("miejsce_zaladunku"),
                        order_data.get("miejsce_rozladunku"),
                        fracht_eur,
                        is_storno,
                        order_data.get("full_trip_price"),
                        order_data.get("source_file"),
                    ),
                )
            return True, "inserted"
        except sqlite3.IntegrityError:
            return False, "duplicate"
        except Exception as e:
            return False, str(e)

    def update_order(self, order_id: int, order_data: dict) -> bool:
        """Update an existing order by its primary key."""
        allowed = {
            "zlecenie_nr", "termin_rozladunku", "miejsce_zaladunku",
            "miejsce_rozladunku", "fracht_eur", "is_storno",
            "full_trip_price", "source_file", "row_number",
        }
        updates = {k: v for k, v in order_data.items() if k in allowed}
        if not updates:
            return False
        set_clause = ", ".join(f"{col} = ?" for col in updates)
        values = list(updates.values()) + [order_id]
        try:
            with self.conn:
                self.conn.execute(
                    f"UPDATE orders SET {set_clause} WHERE id = ?", values
                )
            return True
        except Exception:
            return False

    def delete_order(self, order_id: int) -> bool:
        """Delete an order by primary key."""
        try:
            with self.conn:
                self.conn.execute("DELETE FROM orders WHERE id = ?", (order_id,))
            return True
        except Exception:
            return False

    def order_exists(self, zlecenie_nr: str, week_table_id: int) -> bool:
        """Check whether an order with the same zlecenie_nr exists in this week."""
        row = self.conn.execute(
            "SELECT 1 FROM orders WHERE zlecenie_nr = ? AND week_table_id = ?",
            (zlecenie_nr, week_table_id),
        ).fetchone()
        return row is not None

    def get_orders_by_week(self, week_table_id: int) -> list[dict]:
        """Return orders for a week table, sorted by row_number."""
        rows = self.conn.execute(
            """SELECT * FROM orders
               WHERE week_table_id = ?
               ORDER BY row_number""",
            (week_table_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_orders_by_truck(self, truck_id: int) -> list[dict]:
        """Return all orders for a truck across all weeks, sorted by date."""
        rows = self.conn.execute(
            """SELECT o.*, wt.week_identifier, wt.eur_pln_rate
               FROM orders o
               JOIN week_tables wt ON o.week_table_id = wt.id
               WHERE wt.truck_id = ?
               ORDER BY o.termin_rozladunku""",
            (truck_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_all_orders(self) -> list[dict]:
        """Return every order with truck plate and week info, sorted by plate then date."""
        rows = self.conn.execute(
            """SELECT o.*, t.plate, wt.week_identifier, wt.eur_pln_rate
               FROM orders o
               JOIN week_tables wt ON o.week_table_id = wt.id
               JOIN trucks t ON wt.truck_id = t.id
               ORDER BY t.plate, o.termin_rozladunku"""
        ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search_orders(self, query: str) -> list[dict]:
        """Case-insensitive partial match across text fields."""
        like = f"%{query}%"
        rows = self.conn.execute(
            """SELECT o.*, t.plate, wt.week_identifier, wt.eur_pln_rate
               FROM orders o
               JOIN week_tables wt ON o.week_table_id = wt.id
               JOIN trucks t ON wt.truck_id = t.id
               WHERE o.zlecenie_nr       LIKE ? COLLATE NOCASE
                  OR o.miejsce_zaladunku  LIKE ? COLLATE NOCASE
                  OR o.miejsce_rozladunku LIKE ? COLLATE NOCASE
                  OR o.source_file        LIKE ? COLLATE NOCASE
                  OR t.plate              LIKE ? COLLATE NOCASE
               ORDER BY t.plate, o.termin_rozladunku""",
            (like, like, like, like, like),
        ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Computed Week Summary
    # ------------------------------------------------------------------

    def get_week_summary(self, week_table_id: int) -> dict:
        """Compute all summary values for a week table.

        Returns dict with keys:
            km_total, fuel_refueled, km_in_germany, eur_pln_rate,
            extra_highway_charge_eur,
            order_count, suma_eur, suma_pln,
            fuel_consumption, auto_de_eur, auto_de_pln,
            suma_po_aut_eur, suma_po_aut_pln,
            stawka_eur, stawka_pln,
            po_aut_eur, po_aut_pln
        """
        wt = self.get_week_table(week_table_id)
        if not wt:
            return {}

        orders = self.get_orders_by_week(week_table_id)

        km = wt["km_total"] or 0
        fuel = wt["fuel_refueled"] or 0
        km_de = wt["km_in_germany"] or 0
        rate = wt["eur_pln_rate"] or 4.25
        extra = wt["extra_highway_charge_eur"] or 0

        suma_eur = sum(o["fracht_eur"] or 0 for o in orders)
        suma_pln = suma_eur * rate

        fuel_consumption = (fuel / km * 100) if km > 0 else 0
        auto_de_eur = km_de * 0.35 + extra
        auto_de_pln = rate * auto_de_eur

        suma_po_aut_eur = suma_eur - auto_de_eur
        suma_po_aut_pln = suma_pln - auto_de_pln

        stawka_eur = (suma_eur / km) if km > 0 else 0
        stawka_pln = (suma_pln / km) if km > 0 else 0
        po_aut_eur = (suma_po_aut_eur / km) if km > 0 else 0
        po_aut_pln = (suma_po_aut_pln / km) if km > 0 else 0

        return {
            "week_table_id": week_table_id,
            "week_identifier": wt["week_identifier"],
            "km_total": km,
            "fuel_refueled": fuel,
            "km_in_germany": km_de,
            "eur_pln_rate": rate,
            "extra_highway_charge_eur": extra,
            "order_count": len(orders),
            "suma_eur": round(suma_eur, 2),
            "suma_pln": round(suma_pln, 2),
            "fuel_consumption": round(fuel_consumption, 2),
            "auto_de_eur": round(auto_de_eur, 2),
            "auto_de_pln": round(auto_de_pln, 2),
            "suma_po_aut_eur": round(suma_po_aut_eur, 2),
            "suma_po_aut_pln": round(suma_po_aut_pln, 2),
            "stawka_eur": round(stawka_eur, 2),
            "stawka_pln": round(stawka_pln, 2),
            "po_aut_eur": round(po_aut_eur, 2),
            "po_aut_pln": round(po_aut_pln, 2),
        }

    # ------------------------------------------------------------------
    # Global Statistics
    # ------------------------------------------------------------------

    def get_statistics(self) -> dict:
        """Return overall statistics across all trucks and weeks.

        Keys: total_orders, unique_plates, total_fracht_eur, avg_fracht_eur,
              orders_per_month, date_range, missing_fields, fracht_per_plate.
        """
        all_orders = self.get_all_orders()
        total = len(all_orders)

        plates = set()
        total_fracht = 0.0
        orders_per_month: dict[str, int] = {}
        dates: list[str] = []
        missing: dict[str, int] = {
            "zlecenie_nr": 0,
            "termin_rozladunku": 0,
            "miejsce_zaladunku": 0,
            "miejsce_rozladunku": 0,
            "fracht_eur": 0,
        }
        fracht_per_plate: dict[str, dict] = {}

        for o in all_orders:
            plate = o.get("plate", "?")
            plates.add(plate)

            fracht = o.get("fracht_eur") or 0
            total_fracht += fracht

            # fracht per plate
            if plate not in fracht_per_plate:
                fracht_per_plate[plate] = {"order_count": 0, "total_fracht": 0.0}
            fracht_per_plate[plate]["order_count"] += 1
            fracht_per_plate[plate]["total_fracht"] += fracht

            # per month
            dt = o.get("termin_rozladunku")
            if dt and len(dt) >= 7:
                month_key = dt[:7]  # "YYYY-MM"
                orders_per_month[month_key] = orders_per_month.get(month_key, 0) + 1
                dates.append(dt)

            # missing
            for field in missing:
                if not o.get(field):
                    missing[field] += 1

        avg_fracht = (total_fracht / total) if total > 0 else 0

        # Compute avg per plate
        for p in fracht_per_plate.values():
            cnt = p["order_count"]
            p["avg_fracht"] = round(p["total_fracht"] / cnt, 2) if cnt > 0 else 0

        return {
            "total_orders": total,
            "unique_plates": len(plates),
            "total_fracht_eur": round(total_fracht, 2),
            "avg_fracht_eur": round(avg_fracht, 2),
            "orders_per_month": dict(sorted(orders_per_month.items())),
            "date_range": {
                "min_date": min(dates) if dates else None,
                "max_date": max(dates) if dates else None,
            },
            "missing_fields": missing,
            "fracht_per_plate": fracht_per_plate,
        }

    def get_unique_plates(self) -> list[str]:
        """Return sorted list of unique license plates."""
        rows = self.conn.execute(
            "SELECT plate FROM trucks ORDER BY plate"
        ).fetchall()
        return [r["plate"] for r in rows]

    # ------------------------------------------------------------------
    # Week-Identifier Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def parse_week_identifier(identifier: str):
        """Parse week identifier into (monday_date, sunday_date) or None.

        Supports formats:
          - Cross-month: 'YYYY-MM.DD-MM.DD'  e.g. '2026-03.30-04.05'
          - Same-month:  'YYYY-MM.DD-DD'      e.g. '2026-03.23-29'
          - Legacy:      'MM.DD-DD'            e.g. '3.23-29' (assumes current year)
        Returns (monday: date, sunday: date) or None.
        """
        import re
        from datetime import date as _date

        s = identifier.strip()

        # Cross-month: YYYY-MM.DD-MM.DD  e.g. 2026-03.30-04.05
        m = re.match(r"^(\d{4})-(\d{1,2})\.(\d{1,2})-(\d{1,2})\.(\d{1,2})$", s)
        if m:
            yr = int(m.group(1))
            m1, d1, m2, d2 = int(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(5))
            try:
                yr2 = yr + 1 if m2 < m1 else yr  # handle Dec→Jan
                return _date(yr, m1, d1), _date(yr2, m2, d2)
            except ValueError:
                return None

        # Same-month: YYYY-MM.DD-DD  e.g. 2026-03.23-29
        m = re.match(r"^(\d{4})-(\d{1,2})\.(\d{1,2})-(\d{1,2})$", s)
        if m:
            yr, mo = int(m.group(1)), int(m.group(2))
            d1, d2 = int(m.group(3)), int(m.group(4))
            try:
                return _date(yr, mo, d1), _date(yr, mo, d2)
            except ValueError:
                return None

        # Legacy: MM.DD-DD  e.g. 3.23-29
        m = re.match(r"^(\d{1,2})\.(\d{1,2})-(\d{1,2})$", s)
        if m:
            mo, d1, d2 = int(m.group(1)), int(m.group(2)), int(m.group(3))
            yr = _date.today().year
            try:
                return _date(yr, mo, d1), _date(yr, mo, d2)
            except ValueError:
                return None

        return None

    @staticmethod
    def _make_week_id(monday, next_monday):
        """Generate a week identifier string: MM.DD-DD or MM.DD-MM.DD."""
        if monday.month == next_monday.month:
            return f"{monday.year}-{monday.month:02d}.{monday.day:02d}-{next_monday.day:02d}"
        else:
            return f"{monday.year}-{monday.month:02d}.{monday.day:02d}-{next_monday.month:02d}.{next_monday.day:02d}"

    def find_or_create_week_table(
        self,
        truck_id: int,
        order_date: str,
        eur_pln_rate: float = 4.25,
    ) -> int:
        """Find an existing week table whose Monday-to-Monday range covers
        *order_date*, or create a new one.

        Weeks run Monday → next Monday (exclusive). Cross-month weeks are
        handled correctly (e.g. '2026-03.30-04.06').

        Returns the week_table id.
        """
        from datetime import timedelta
        from datetime import date as _date

        try:
            dt = datetime.strptime(order_date, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return self.add_week_table(
                truck_id, "unknown", eur_pln_rate=eur_pln_rate,
            )

        # Find Monday of this week and next Monday
        monday = dt - timedelta(days=dt.weekday())   # weekday: 0=Mon
        next_monday = monday + timedelta(days=7)
        week_id = self._make_week_id(monday, next_monday)

        # Check existing week tables (exact match first)
        week_tables = self.get_week_tables(truck_id)
        for wt in week_tables:
            if wt["week_identifier"] == week_id:
                return wt["id"]

        # Backward compat: check if order date falls in any existing week's range
        for wt in week_tables:
            parsed = self.parse_week_identifier(wt["week_identifier"])
            if parsed:
                wk_start, wk_end = parsed
                if wk_start <= dt < wk_end:  # < not <= (end is exclusive)
                    return wt["id"]

        return self.add_week_table(
            truck_id, week_id, eur_pln_rate=eur_pln_rate,
        )

    # ------------------------------------------------------------------
    # Export helpers
    # ------------------------------------------------------------------

    def export_orders_for_csv(self, week_table_id: Optional[int] = None) -> list[dict]:
        """Return orders enriched with plate, week, and price_pln.

        If *week_table_id* is given, only that week's orders are returned.
        """
        if week_table_id:
            orders = self.get_orders_by_week(week_table_id)
            wt = self.get_week_table(week_table_id)
            rate = wt["eur_pln_rate"] if wt else 4.25
            truck = self.conn.execute(
                "SELECT plate FROM trucks WHERE id = ?", (wt["truck_id"],)
            ).fetchone() if wt else None
            plate = truck["plate"] if truck else "?"
            for o in orders:
                o["plate"] = plate
                o["eur_pln_rate"] = rate
                o["price_pln"] = round((o["fracht_eur"] or 0) * rate, 2)
            return orders
        else:
            all_orders = self.get_all_orders()
            for o in all_orders:
                rate = o.get("eur_pln_rate", 4.25) or 4.25
                o["price_pln"] = round((o["fracht_eur"] or 0) * rate, 2)
            return all_orders

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
