import re
import sqlite3
from datetime import datetime
from pathlib import Path

from config import config


class Database:
    SHIPMENT_STATUSES = {"forming", "sent_from_china", "arrived", "sorted", "closed"}

    def __init__(self, path: Path | str | None = None):
        self.path = Path(path or config.db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()
        try:
            self.path.chmod(0o600)
        except OSError:
            pass

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    @staticmethod
    def _now() -> str:
        return datetime.now().strftime("%d.%m.%Y %H:%M")

    @staticmethod
    def _row(row: sqlite3.Row | None) -> dict | None:
        return dict(row) if row else None

    @staticmethod
    def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
        return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value REAL NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS orders (
                    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    weight_kg REAL NOT NULL,
                    city_name TEXT NOT NULL,
                    city_code TEXT NOT NULL,
                    price_cny REAL NOT NULL DEFAULT 0,
                    goods_rub REAL NOT NULL DEFAULT 0,
                    service_fee_rub REAL NOT NULL DEFAULT 0,
                    usd_rate REAL NOT NULL DEFAULT 0,
                    total_rub REAL NOT NULL DEFAULT 0,
                    item_desc TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'pending',
                    reject_reason TEXT,
                    shipment_id INTEGER,
                    created_at TEXT NOT NULL,
                    deleted_by_user INTEGER NOT NULL DEFAULT 0,
                    in_pool INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS order_trackers (
                    order_id INTEGER NOT NULL,
                    tracker TEXT NOT NULL,
                    PRIMARY KEY(order_id, tracker),
                    FOREIGN KEY(order_id) REFERENCES orders(order_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS shipments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    city_name TEXT NOT NULL,
                    name TEXT NOT NULL,
                    track_number TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'forming',
                    created_at TEXT NOT NULL,
                    arrived_at TEXT,
                    arrival_notified_at TEXT,
                    status_updated_at TEXT
                );

                CREATE TABLE IF NOT EXISTS banned_users (
                    user_id INTEGER PRIMARY KEY,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS user_preferences (
                    user_id INTEGER PRIMARY KEY,
                    pool_notifications INTEGER NOT NULL DEFAULT 1 CHECK(pool_notifications IN (0, 1)),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS order_media (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER NOT NULL,
                    file_id TEXT NOT NULL,
                    file_unique_id TEXT NOT NULL,
                    source TEXT NOT NULL CHECK(source IN ('client_item', 'warehouse')),
                    uploaded_by INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    caption TEXT NOT NULL DEFAULT '',
                    FOREIGN KEY(order_id) REFERENCES orders(order_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS admin_order_notifications (
                    order_id INTEGER NOT NULL,
                    admin_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    message_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(order_id, admin_id),
                    FOREIGN KEY(order_id) REFERENCES orders(order_id) ON DELETE CASCADE
                );
                """
            )
            columns = self._columns(conn, "orders")
            additions = {
                "recipient_name": "TEXT NOT NULL DEFAULT ''",
                "recipient_address": "TEXT NOT NULL DEFAULT ''",
                "recipient_phone": "TEXT NOT NULL DEFAULT ''",
                "delivery_method": "TEXT NOT NULL DEFAULT ''",
                "status_message": "TEXT NOT NULL DEFAULT ''",
                "delivered_at": "TEXT",
                "sent_to_client_at": "TEXT",
                "shipment_arrival_notified_at": "TEXT",
            }
            for name, ddl in additions.items():
                if name not in columns:
                    conn.execute(f"ALTER TABLE orders ADD COLUMN {name} {ddl}")

            shipment_columns = self._columns(conn, "shipments")
            for name, ddl in {
                "arrived_at": "TEXT",
                "arrival_notified_at": "TEXT",
                "status_updated_at": "TEXT",
            }.items():
                if name not in shipment_columns:
                    conn.execute(f"ALTER TABLE shipments ADD COLUMN {name} {ddl}")

            # Переводим старые значения в стабильные внутренние коды. Клиенту они
            # никогда не показываются напрямую — отображение локализуется в UI.
            conn.execute("UPDATE shipments SET status='sent_from_china' WHERE status='отправлен'")
            conn.execute("UPDATE shipments SET status='arrived' WHERE status='прибыл'")

            media_columns = self._columns(conn, "order_media")
            if "caption" not in media_columns:
                conn.execute("ALTER TABLE order_media ADD COLUMN caption TEXT NOT NULL DEFAULT ''")

            if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='shipment_orders'").fetchone():
                links = conn.execute("SELECT shipment_id, order_id FROM shipment_orders").fetchall()
                for link in links:
                    conn.execute(
                        "UPDATE orders SET shipment_id=? WHERE order_id=? AND shipment_id IS NULL",
                        (link["shipment_id"], link["order_id"]),
                    )
                conn.execute("DROP TABLE shipment_orders")

            conn.executescript(
                """
                CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id, order_id DESC);
                CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status, order_id DESC);
                CREATE INDEX IF NOT EXISTS idx_orders_pool ON orders(in_pool, city_code);
                CREATE INDEX IF NOT EXISTS idx_orders_shipment ON orders(shipment_id, order_id);
                CREATE INDEX IF NOT EXISTS idx_order_media_order ON order_media(order_id, id);
                CREATE INDEX IF NOT EXISTS idx_admin_order_notifications_order ON admin_order_notifications(order_id);
                """
            )

            conn.execute(
                """
                UPDATE orders
                SET shipment_id=NULL,
                    status=CASE WHEN status='shipped' THEN 'accepted' ELSE status END,
                    in_pool=CASE WHEN city_code='vlg' AND status='shipped' THEN 1 ELSE in_pool END
                WHERE shipment_id IS NOT NULL
                  AND NOT EXISTS (SELECT 1 FROM shipments s WHERE s.id=orders.shipment_id)
                """
            )

            now = self._now()
            defaults = {
                "cny_low": config.legacy_cny_low,
                "cny_high": config.legacy_cny_high,
                "usd": config.legacy_usd,
                "broker_cny": config.legacy_cny_low,
            }
            conn.executemany(
                "INSERT OR IGNORE INTO settings(key, value, updated_at) VALUES(?, ?, ?)",
                [(key, value, now) for key, value in defaults.items()],
            )

    @staticmethod
    def _reset_sequence(conn: sqlite3.Connection, table: str, id_column: str) -> None:
        """Не учитывать уже удалённые максимальные номера AUTOINCREMENT."""
        max_id = int(conn.execute(f"SELECT COALESCE(MAX({id_column}), 0) AS n FROM {table}").fetchone()["n"])
        if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='sqlite_sequence'").fetchone():
            conn.execute("DELETE FROM sqlite_sequence WHERE name=?", (table,))
            if max_id:
                conn.execute("INSERT INTO sqlite_sequence(name, seq) VALUES(?, ?)", (table, max_id))

    @staticmethod
    def _cargo_sort_key(order: dict) -> tuple:
        shipment = order.get("shipment")
        if not shipment:
            return (1, (), -int(order["order_id"]))
        track = str(shipment.get("track_number") or "")
        parts = tuple((0, int(part)) if part.isdigit() else (1, part.casefold()) for part in re.split(r"(\d+)", track))
        return (0, parts, int(order["order_id"]))

    def _with_order_details(self, conn: sqlite3.Connection, order: dict | None) -> dict | None:
        if not order:
            return None
        rows = conn.execute(
            "SELECT tracker FROM order_trackers WHERE order_id=? ORDER BY rowid",
            (order["order_id"],),
        ).fetchall()
        order["trackers"] = [row["tracker"] for row in rows]
        media_rows = conn.execute(
            "SELECT id, file_id, file_unique_id, source, uploaded_by, created_at, caption FROM order_media WHERE order_id=? ORDER BY id",
            (order["order_id"],),
        ).fetchall()
        order["media"] = [dict(row) for row in media_rows]
        order["deleted_by_user"] = bool(order.get("deleted_by_user"))
        order["in_pool"] = bool(order.get("in_pool"))
        order["shipment"] = None
        if order.get("shipment_id"):
            shipment = conn.execute("SELECT * FROM shipments WHERE id=?", (order["shipment_id"],)).fetchone()
            if shipment:
                order["shipment"] = dict(shipment)
        return order

    def get_rates(self) -> dict[str, float]:
        with self._connect() as conn:
            rows = conn.execute("SELECT key, value FROM settings").fetchall()
        values = {row["key"]: float(row["value"]) for row in rows}
        return {
            "cny_low": values.get("cny_low", config.legacy_cny_low),
            "cny_high": values.get("cny_high", config.legacy_cny_high),
            "usd": values.get("usd", config.legacy_usd),
            "broker_cny": values.get("broker_cny", config.legacy_cny_low),
        }

    def update_rate(self, key: str, value: float) -> None:
        if key not in {"cny_low", "cny_high", "usd", "broker_cny"}:
            raise ValueError("Неизвестный курс")
        if not 0 < value < 10000:
            raise ValueError("Некорректный курс")
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO settings(key, value, updated_at) VALUES(?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                (key, round(float(value), 4), self._now()),
            )

    def create_order(
        self,
        user_id: int,
        weight_kg: float,
        city_name: str,
        city_code: str,
        price_cny: float,
        goods_rub: float,
        service_fee_rub: float,
        usd_rate: float,
        total_rub: float,
        item_desc: str = "",
        recipient_name: str = "",
        recipient_address: str = "",
        recipient_phone: str = "",
        delivery_method: str = "",
    ) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO orders(
                    user_id, weight_kg, city_name, city_code, price_cny, goods_rub,
                    service_fee_rub, usd_rate, total_rub, item_desc, created_at,
                    recipient_name, recipient_address, recipient_phone, delivery_method
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(user_id), round(weight_kg, 2), city_name[:100], city_code.lower(),
                    float(price_cny), float(goods_rub), float(service_fee_rub),
                    float(usd_rate), round(total_rub, 2), item_desc[:1500], self._now(),
                    recipient_name[:200], recipient_address[:500], recipient_phone[:100], delivery_method[:100],
                ),
            )
            return int(cur.lastrowid)

    def get_order(self, order_id: int) -> dict | None:
        with self._connect() as conn:
            order = self._row(conn.execute("SELECT * FROM orders WHERE order_id=?", (int(order_id),)).fetchone())
            return self._with_order_details(conn, order)

    def save_admin_order_notification(self, order_id: int, admin_id: int, chat_id: int, message_id: int) -> bool:
        with self._connect() as conn:
            if not conn.execute("SELECT 1 FROM orders WHERE order_id=?", (int(order_id),)).fetchone():
                return False
            conn.execute(
                """
                INSERT INTO admin_order_notifications(order_id, admin_id, chat_id, message_id, created_at)
                VALUES(?, ?, ?, ?, ?)
                ON CONFLICT(order_id, admin_id) DO UPDATE SET
                    chat_id=excluded.chat_id,
                    message_id=excluded.message_id,
                    created_at=excluded.created_at
                """,
                (int(order_id), int(admin_id), int(chat_id), int(message_id), self._now()),
            )
            return True

    def get_admin_order_notifications(self, order_id: int) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT admin_id, chat_id, message_id FROM admin_order_notifications WHERE order_id=? ORDER BY admin_id",
                (int(order_id),),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_user_order(self, user_id: int, order_id: int) -> dict | None:
        with self._connect() as conn:
            order = self._row(
                conn.execute(
                    "SELECT * FROM orders WHERE order_id=? AND user_id=?",
                    (int(order_id), int(user_id)),
                ).fetchone()
            )
            return self._with_order_details(conn, order)

    def list_recent_orders(self, limit: int | None = None, status: str | None = None) -> list[dict]:
        allowed = {"pending", "accepted", "rejected", "shipped", "delivered"}
        if status is not None and status not in allowed:
            raise ValueError("Некорректный статус тикета")
        with self._connect() as conn:
            if status is None:
                rows = conn.execute("SELECT * FROM orders").fetchall()
            else:
                rows = conn.execute("SELECT * FROM orders WHERE status=?", (status,)).fetchall()
            orders = [self._with_order_details(conn, dict(row)) for row in rows]
        sorted_orders = sorted(orders, key=self._cargo_sort_key)
        if limit is None:
            return sorted_orders
        return sorted_orders[:max(1, int(limit))]

    def search_orders(self, query: str, limit: int = 50) -> list[dict]:
        """Поиск по ID, карго, трекеру, телефону, Telegram ID и ФИО."""
        needle = str(query or "").strip().casefold()
        if not needle:
            return []
        needle_digits = re.sub(r"\D", "", needle)
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM orders ORDER BY order_id DESC").fetchall()
            found = []
            for row in rows:
                order = self._with_order_details(conn, dict(row))
                shipment = order.get("shipment") or {}
                haystack = [
                    str(order.get("order_id") or ""),
                    str(order.get("user_id") or ""),
                    str(order.get("recipient_name") or ""),
                    str(order.get("recipient_phone") or ""),
                    str(shipment.get("track_number") or ""),
                    str(shipment.get("name") or ""),
                    *(str(x) for x in order.get("trackers", [])),
                ]
                phone_digits = re.sub(r"\D", "", str(order.get("recipient_phone") or ""))
                phone_match = bool(needle_digits and len(needle_digits) >= 4 and needle_digits in phone_digits)
                if phone_match or any(needle in value.casefold() for value in haystack):
                    found.append(order)
                    if len(found) >= max(1, min(int(limit), 100)):
                        break
        return found

    def ensure_user(self, user_id: int) -> None:
        user_id = int(user_id)
        if user_id <= 0:
            return
        now = self._now()
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO user_preferences(user_id, pool_notifications, created_at, updated_at) VALUES(?, 1, ?, ?)",
                (user_id, now, now),
            )

    def pool_notifications_enabled(self, user_id: int) -> bool:
        self.ensure_user(user_id)
        with self._connect() as conn:
            row = conn.execute("SELECT pool_notifications FROM user_preferences WHERE user_id=?", (int(user_id),)).fetchone()
            return bool(row["pool_notifications"]) if row else True

    def set_pool_notifications(self, user_id: int, enabled: bool) -> None:
        self.ensure_user(user_id)
        with self._connect() as conn:
            conn.execute(
                "UPDATE user_preferences SET pool_notifications=?, updated_at=? WHERE user_id=?",
                (1 if enabled else 0, self._now(), int(user_id)),
            )

    def pool_notification_recipients(self) -> list[int]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT user_id FROM user_preferences WHERE pool_notifications=1
                UNION
                SELECT DISTINCT o.user_id
                FROM orders o
                WHERE NOT EXISTS (
                    SELECT 1 FROM user_preferences p
                    WHERE p.user_id=o.user_id AND p.pool_notifications=0
                )
                ORDER BY user_id
                """
            ).fetchall()
            banned = {int(row["user_id"]) for row in conn.execute("SELECT user_id FROM banned_users").fetchall()}
        return [
            int(row["user_id"]) for row in rows
            if int(row["user_id"]) not in banned and not config.is_admin(int(row["user_id"]))
        ]

    def get_user_orders(self, user_id: int, limit: int = 12) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM orders WHERE user_id=?",
                (int(user_id),),
            ).fetchall()
            orders = [self._with_order_details(conn, dict(row)) for row in rows]
        return sorted(orders, key=self._cargo_sort_key)[:max(1, min(int(limit), 50))]

    def get_accepted_orders(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM orders WHERE status IN ('accepted', 'shipped', 'delivered')").fetchall()
            orders = [self._with_order_details(conn, dict(row)) for row in rows]
        return sorted(orders, key=self._cargo_sort_key)

    def set_status(self, order_id: int, status: str, reject_reason: str | None = None) -> bool:
        if status not in {"pending", "accepted", "rejected", "shipped", "delivered"}:
            raise ValueError("Некорректный статус")
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE orders SET status=?, reject_reason=? WHERE order_id=?",
                (status, reject_reason[:1000] if reject_reason else None, int(order_id)),
            )
            return cur.rowcount > 0

    def accept_order(self, order_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE orders
                SET status='accepted', reject_reason=NULL,
                    in_pool=CASE WHEN city_code='vlg' THEN 1 ELSE 0 END
                WHERE order_id=? AND status='pending'
                """,
                (int(order_id),),
            )
            return cur.rowcount == 1

    def reject_pending_order(self, order_id: int, reason: str | None) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE orders
                SET status='rejected', reject_reason=?, in_pool=0, shipment_id=NULL, sent_to_client_at=NULL, shipment_arrival_notified_at=NULL
                WHERE order_id=? AND status='pending'
                """,
                (reason[:1000] if reason else None, int(order_id)),
            )
            return cur.rowcount == 1

    def reject_order(self, order_id: int, reason: str | None) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE orders SET status='rejected', reject_reason=?, in_pool=0, shipment_id=NULL, sent_to_client_at=NULL, shipment_arrival_notified_at=NULL WHERE order_id=?",
                (reason[:1000] if reason else None, int(order_id)),
            )
            return cur.rowcount > 0

    def restore_order(self, order_id: int) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT city_code, status FROM orders WHERE order_id=?", (int(order_id),)).fetchone()
            if not row or row["status"] != "rejected":
                return False
            conn.execute(
                "UPDATE orders SET status='accepted', reject_reason=NULL, in_pool=? WHERE order_id=?",
                (1 if row["city_code"] == "vlg" else 0, int(order_id)),
            )
            return True

    def update_weight(self, order_id: int, new_weight: float) -> tuple[float, float, float] | None:
        if not 0 < new_weight <= config.max_weight_kg:
            return None
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM orders WHERE order_id=?", (int(order_id),)).fetchone()
            if not row:
                return None
            old_weight = float(row["weight_kg"])
            rate_usd_kg = config.delivery_msk_usd_kg if row["city_code"] == "msk" else config.delivery_vlg_usd_kg
            delivery_rub = round(new_weight * rate_usd_kg * float(row["usd_rate"]), 2)
            total = round(float(row["goods_rub"]) + float(row["service_fee_rub"]) + delivery_rub, 2)
            conn.execute("UPDATE orders SET weight_kg=?, total_rub=? WHERE order_id=?", (round(new_weight, 2), total, int(order_id)))
            return old_weight, round(new_weight, 2), total

    def add_tracker(self, order_id: int, tracker: str) -> bool:
        tracker = tracker.strip()[:200]
        if not tracker:
            return False
        with self._connect() as conn:
            if not conn.execute("SELECT 1 FROM orders WHERE order_id=?", (int(order_id),)).fetchone():
                return False
            conn.execute("INSERT OR IGNORE INTO order_trackers(order_id, tracker) VALUES(?, ?)", (int(order_id), tracker))
            return True

    def remove_tracker(self, order_id: int, tracker: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM order_trackers WHERE order_id=? AND tracker=?", (int(order_id), tracker.strip()))
            return cur.rowcount > 0

    def delete_order(self, order_id: int) -> dict | None:
        with self._connect() as conn:
            order = self._row(conn.execute("SELECT * FROM orders WHERE order_id=?", (int(order_id),)).fetchone())
            if not order:
                return None
            order = self._with_order_details(conn, order)
            conn.execute("DELETE FROM orders WHERE order_id=?", (int(order_id),))
            self._reset_sequence(conn, "orders", "order_id")
            self._reset_sequence(conn, "order_media", "id")
            return order

    def clear_orders_and_shipments(self) -> None:
        """Полная очистка рабочих сущностей с возвратом нумерации к 1."""
        with self._connect() as conn:
            conn.execute("DELETE FROM orders")
            conn.execute("DELETE FROM shipments")
            self._reset_sequence(conn, "orders", "order_id")
            self._reset_sequence(conn, "shipments", "id")
            self._reset_sequence(conn, "order_media", "id")

    def pool_info(self) -> dict:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT order_id, weight_kg FROM orders WHERE city_code='vlg' AND in_pool=1 AND shipment_id IS NULL ORDER BY order_id"
            ).fetchall()
        current = round(sum(float(row["weight_kg"]) for row in rows), 2)
        return {
            "current": current,
            "target": config.target_pool_weight,
            "remaining": max(0.0, round(config.target_pool_weight - current, 2)),
            "order_ids": [int(row["order_id"]) for row in rows],
        }

    def reset_pool(self) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE orders SET in_pool=0 WHERE city_code='vlg' AND in_pool=1 AND shipment_id IS NULL")

    def create_shipment(self, city_name: str, name: str, order_ids: list[int], track_number: str) -> int:
        clean_ids = list(dict.fromkeys(int(x) for x in order_ids if int(x) > 0))
        if not clean_ids:
            raise ValueError("Пустое отправление")
        city_code = "msk" if city_name.lower().startswith("моск") else "vlg"
        with self._connect() as conn:
            placeholders = ",".join("?" for _ in clean_ids)
            rows = conn.execute(
                f"SELECT order_id, city_code, status, shipment_id FROM orders WHERE order_id IN ({placeholders})",
                clean_ids,
            ).fetchall()
            if len(rows) != len(clean_ids):
                raise ValueError("Один или несколько тикетов не найдены")
            for row in rows:
                if row["city_code"] != city_code:
                    raise ValueError(f"Тикет #{row['order_id']} относится к другому городу")
                if row["status"] != "accepted":
                    raise ValueError(f"Тикет #{row['order_id']} должен быть принят перед добавлением в отправление")
                if row["shipment_id"] is not None:
                    raise ValueError(f"Тикет #{row['order_id']} уже находится в отправлении #{row['shipment_id']}")
            now = self._now()
            cur = conn.execute(
                "INSERT INTO shipments(city_name, name, track_number, status, created_at, status_updated_at) VALUES(?, ?, ?, 'forming', ?, ?)",
                (city_name[:100], name[:200], track_number[:200], now, now),
            )
            shipment_id = int(cur.lastrowid)
            conn.executemany(
                "UPDATE orders SET shipment_id=?, in_pool=0, status_message='Отправление формируется.', sent_to_client_at=NULL, shipment_arrival_notified_at=NULL, delivered_at=NULL WHERE order_id=?",
                [(shipment_id, oid) for oid in clean_ids],
            )
            return shipment_id

    def set_shipment_status(self, shipment_id: int, status: str) -> dict | None:
        status = str(status or "").strip()
        if status not in self.SHIPMENT_STATUSES:
            raise ValueError("Некорректный статус отправления")
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM shipments WHERE id=?", (int(shipment_id),)).fetchone()
            if not row:
                return None
            now = self._now()
            city = row["city_name"]
            messages = {
                "forming": "Отправление формируется.",
                "sent_from_china": "Отправление отправлено из Китая.",
                "arrived": f"Отправление прибыло в {city}.",
                "sorted": f"Отправление разобрано в {city}.",
                "closed": "Отправление закрыто.",
            }
            arrived_at = row["arrived_at"]
            if status in {"arrived", "sorted", "closed"}:
                arrived_at = arrived_at or now
            elif status in {"forming", "sent_from_china"}:
                arrived_at = None
            conn.execute(
                "UPDATE shipments SET status=?, status_updated_at=?, arrived_at=?, arrival_notified_at=NULL WHERE id=?",
                (status, now, arrived_at, int(shipment_id)),
            )
            if status == "forming":
                conn.execute(
                    "UPDATE orders SET status='accepted', status_message=?, sent_to_client_at=NULL, shipment_arrival_notified_at=NULL WHERE shipment_id=? AND status!='delivered'",
                    (messages[status], int(shipment_id)),
                )
            else:
                conn.execute(
                    "UPDATE orders SET status='shipped', status_message=?, shipment_arrival_notified_at=NULL WHERE shipment_id=? AND status!='delivered'",
                    (messages[status], int(shipment_id)),
                )
        return self.get_shipment(shipment_id)

    def get_shipment(self, shipment_id: int) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM shipments WHERE id=?", (int(shipment_id),)).fetchone()
            if not row:
                return None
            result = dict(row)
            order_rows = conn.execute("SELECT * FROM orders WHERE shipment_id=? ORDER BY order_id", (int(shipment_id),)).fetchall()
            result["orders"] = [self._with_order_details(conn, dict(x)) for x in order_rows]
            result["order_ids"] = [int(x["order_id"]) for x in order_rows]
            return result

    def list_shipments(self, limit: int = 20) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM shipments ORDER BY track_number COLLATE NOCASE, id DESC LIMIT ?",
                (max(1, min(int(limit), 50)),),
            ).fetchall()
            result = []
            for row in rows:
                item = dict(row)
                order_rows = conn.execute("SELECT order_id FROM orders WHERE shipment_id=? ORDER BY order_id", (item["id"],)).fetchall()
                item["order_ids"] = [int(x["order_id"]) for x in order_rows]
                result.append(item)
            return result

    def delete_shipment(self, shipment_id: int) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM shipments WHERE id=?", (int(shipment_id),)).fetchone()
            if not row:
                return None
            result = dict(row)
            order_rows = conn.execute("SELECT order_id, city_code FROM orders WHERE shipment_id=? ORDER BY order_id", (int(shipment_id),)).fetchall()
            result["order_ids"] = [int(x["order_id"]) for x in order_rows]
            for order in order_rows:
                current = conn.execute("SELECT status FROM orders WHERE order_id=?", (order["order_id"],)).fetchone()
                if current and current["status"] == "delivered":
                    conn.execute(
                        "UPDATE orders SET shipment_id=NULL, in_pool=0 WHERE order_id=?",
                        (order["order_id"],),
                    )
                else:
                    conn.execute(
                        "UPDATE orders SET shipment_id=NULL, status='accepted', status_message='', sent_to_client_at=NULL, shipment_arrival_notified_at=NULL, in_pool=? WHERE order_id=?",
                        (1 if order["city_code"] == "vlg" else 0, order["order_id"]),
                    )
            conn.execute("DELETE FROM shipments WHERE id=?", (int(shipment_id),))
            self._reset_sequence(conn, "shipments", "id")
            return result


    def mark_shipment_arrived(self, shipment_id: int) -> dict | None:
        return self.set_shipment_status(shipment_id, "arrived")

    def mark_shipment_arrival_notified(self, shipment_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE shipments SET arrival_notified_at=? WHERE id=? AND arrived_at IS NOT NULL",
                (self._now(), int(shipment_id)),
            )
            return cur.rowcount > 0

    def mark_order_arrival_notified(self, order_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE orders SET shipment_arrival_notified_at=? WHERE order_id=? AND shipment_id IS NOT NULL",
                (self._now(), int(order_id)),
            )
            return cur.rowcount > 0

    def refresh_shipment_arrival_notified(self, shipment_id: int) -> bool:
        with self._connect() as conn:
            shipment = conn.execute(
                "SELECT arrived_at, arrival_notified_at FROM shipments WHERE id=?",
                (int(shipment_id),),
            ).fetchone()
            if not shipment or not shipment["arrived_at"]:
                return False
            pending = conn.execute(
                """
                SELECT COUNT(*) AS n FROM orders
                WHERE shipment_id=? AND status='shipped' AND shipment_arrival_notified_at IS NULL
                """,
                (int(shipment_id),),
            ).fetchone()["n"]
            if int(pending) == 0:
                if not shipment["arrival_notified_at"]:
                    conn.execute(
                        "UPDATE shipments SET arrival_notified_at=? WHERE id=?",
                        (self._now(), int(shipment_id)),
                    )
                return True
            return False

    def mark_sent_to_client(self, order_id: int) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT o.*, s.arrived_at AS shipment_arrived_at
                FROM orders o
                LEFT JOIN shipments s ON s.id=o.shipment_id
                WHERE o.order_id=?
                """,
                (int(order_id),),
            ).fetchone()
            if (
                not row
                or row["shipment_id"] is None
                or row["status"] != "shipped"
                or not row["shipment_arrived_at"]
            ):
                return None
            if row["sent_to_client_at"]:
                return None
            sent_at = self._now()
            delivery_method = row["delivery_method"] or "выбранную службу доставки"
            status_message = f"Товар прибыл в {row['city_name']} и отправлен вам через {delivery_method}."
            conn.execute(
                "UPDATE orders SET sent_to_client_at=?, status_message=? WHERE order_id=?",
                (sent_at, status_message[:1000], int(order_id)),
            )
        return self.get_order(order_id)


    def add_media(self, order_id: int, file_id: str, file_unique_id: str, source: str, uploaded_by: int, caption: str = "") -> int:
        if source not in {"client_item", "warehouse"}:
            raise ValueError("Некорректный источник медиа")
        file_id = str(file_id).strip()
        file_unique_id = str(file_unique_id).strip()
        if not file_id or not file_unique_id or len(file_id) > 1024 or len(file_unique_id) > 256:
            raise ValueError("Некорректный Telegram file_id")
        caption = str(caption or "").strip()[:1000]
        with self._connect() as conn:
            if not conn.execute("SELECT 1 FROM orders WHERE order_id=?", (int(order_id),)).fetchone():
                raise ValueError("Тикет не найден")
            existing = conn.execute(
                "SELECT id FROM order_media WHERE order_id=? AND file_unique_id=? AND source=?",
                (int(order_id), file_unique_id, source),
            ).fetchone()
            if existing:
                if caption:
                    conn.execute("UPDATE order_media SET caption=? WHERE id=?", (caption, int(existing["id"])))
                return int(existing["id"])
            cur = conn.execute(
                "INSERT INTO order_media(order_id, file_id, file_unique_id, source, uploaded_by, created_at, caption) VALUES(?, ?, ?, ?, ?, ?, ?)",
                (int(order_id), file_id, file_unique_id, source, int(uploaded_by), self._now(), caption),
            )
            return int(cur.lastrowid)

    def get_media(self, media_id: int) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, order_id, file_id, file_unique_id, source, uploaded_by, created_at, caption FROM order_media WHERE id=?",
                (int(media_id),),
            ).fetchone()
            return dict(row) if row else None

    def delete_media(self, media_id: int, order_id: int | None = None) -> dict | None:
        with self._connect() as conn:
            if order_id is None:
                row = conn.execute("SELECT * FROM order_media WHERE id=?", (int(media_id),)).fetchone()
            else:
                row = conn.execute("SELECT * FROM order_media WHERE id=? AND order_id=?", (int(media_id), int(order_id))).fetchone()
            if not row:
                return None
            result = dict(row)
            conn.execute("DELETE FROM order_media WHERE id=?", (int(media_id),))
            return result

    def clear_order_media(self, order_id: int) -> int:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM order_media WHERE order_id=?", (int(order_id),))
            return int(cur.rowcount)

    def set_shipment_update(self, order_id: int, message: str) -> dict | None:
        message = str(message).strip()
        if not message or len(message) > 1000:
            raise ValueError("Сообщение должно быть длиной от 1 до 1000 символов")
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM orders WHERE order_id=?", (int(order_id),)).fetchone()
            if not row or row["shipment_id"] is None or row["status"] not in {"shipped", "delivered"}:
                return None
            conn.execute("UPDATE orders SET status_message=? WHERE order_id=?", (message, int(order_id)))
            return dict(row)

    def mark_delivered(self, order_id: int, message: str | None = None) -> tuple[dict, int] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM orders WHERE order_id=?", (int(order_id),)).fetchone()
            if (
                not row
                or row["shipment_id"] is None
                or row["status"] != "shipped"
                or not row["sent_to_client_at"]
            ):
                return None
            status_message = (message or "Заказ доставлен клиенту.").strip()[:1000]
            conn.execute(
                "UPDATE orders SET status='delivered', status_message=?, delivered_at=?, in_pool=0 WHERE order_id=?",
                (status_message, self._now(), int(order_id)),
            )
            deleted = conn.execute("DELETE FROM order_media WHERE order_id=?", (int(order_id),)).rowcount
            return dict(row), int(deleted)

    def is_banned(self, user_id: int) -> bool:
        if config.is_admin(user_id):
            return False
        with self._connect() as conn:
            return conn.execute("SELECT 1 FROM banned_users WHERE user_id=?", (int(user_id),)).fetchone() is not None

    def ban(self, user_id: int) -> bool:
        if config.is_admin(user_id):
            return False
        with self._connect() as conn:
            conn.execute("INSERT OR IGNORE INTO banned_users(user_id, created_at) VALUES(?, ?)", (int(user_id), self._now()))
            return True

    def unban(self, user_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM banned_users WHERE user_id=?", (int(user_id),))


db = Database()
