#!/usr/bin/env bash
# Back up deliverybot_db, clear it, and insert users with known passwords
# (see seed_users.sql for the list).
#
#   ./reset_database.sh          clears users, orders (+ their products), robot command
#                                history, sensor logs (keeps the product list, table maps,
#                                tables and the robot IP setting)
#   ./reset_database.sh --all    clears EVERY table, including products, table maps and
#                                robot settings (the backend adds the sample products again)
#   ./reset_database.sh --yes    no confirmation question
#
# A full backup is written to backups/ first. To restore it:
#   mysql -u deliverybot_user -p deliverybot_db < backups/<file>.sql
#
# Connection (defaults = backend/src/main/resources/application.properties):
#   DB_USER=deliverybot_user DB_PASS=deliverybot123 DB_NAME=deliverybot_db DB_HOST=127.0.0.1
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

DB_USER=${DB_USER:-deliverybot_user}
DB_NAME=${DB_NAME:-deliverybot_db}
DB_HOST=${DB_HOST:-127.0.0.1}
export MYSQL_PWD=${DB_PASS:-deliverybot123}

ALL=0; YES=0
for a in "$@"; do
    case "$a" in
        --all) ALL=1 ;;
        --yes|-y) YES=1 ;;
        -h|--help) sed -n '2,16p' "$0"; exit 0 ;;
        *) echo "unknown option $a"; exit 1 ;;
    esac
done

MYSQL=(mysql -h "$DB_HOST" -u "$DB_USER" "$DB_NAME")
"${MYSQL[@]}" -e "SELECT 1" >/dev/null || { echo "Cannot connect to MySQL ($DB_USER@$DB_HOST/$DB_NAME). Is it running?"; exit 1; }

if [ "$ALL" = 1 ]; then
    WANTED="users order_items delivery_orders robot_commands sensor_logs products delivery_tables map_configs robot_config"
else
    WANTED="users order_items delivery_orders robot_commands sensor_logs"
fi
# only the tables that exist (order_items/products appear after the backend's first start)
EXISTING=$("${MYSQL[@]}" -N -e "SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE()")
TABLES=""
COUNT_SQL=""
for t in $WANTED; do
    if grep -qx "$t" <<< "$EXISTING"; then
        TABLES+="$t "
        COUNT_SQL+="${COUNT_SQL:+ UNION ALL }SELECT '$t' AS table_name, COUNT(*) AS rows_now FROM $t"
    fi
done
echo "Current rows:"
"${MYSQL[@]}" -t -e "$COUNT_SQL;"
echo "Will clear: $TABLES"
if [ "$YES" != 1 ]; then
    read -r -p "Type yes to continue: " answer
    [ "$answer" = "yes" ] || { echo "Cancelled."; exit 1; }
fi

mkdir -p backups
BACKUP="backups/${DB_NAME}_$(date +%Y%m%d_%H%M%S).sql"
mysqldump -h "$DB_HOST" -u "$DB_USER" --no-tablespaces --single-transaction "$DB_NAME" > "$BACKUP"
echo "Backup written: $BACKUP"

SQL="SET FOREIGN_KEY_CHECKS=0;"
for t in $TABLES; do
    SQL+="DELETE FROM $t; ALTER TABLE $t AUTO_INCREMENT = 1;"
done
SQL+="SET FOREIGN_KEY_CHECKS=1;"
"${MYSQL[@]}" -e "$SQL"
"${MYSQL[@]}" < seed_users.sql

echo "Done. Users now:"
"${MYSQL[@]}" -t -e "SELECT id, email, role FROM users ORDER BY id;"
echo "Passwords: admin123 / operator123 / user123 (see seed_users.sql)."
