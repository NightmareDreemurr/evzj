# 路径自改
$db = "D:\Github\evzj\app.db"

$sql = @"
PRAGMA foreign_keys=ON;
BEGIN;
DELETE FROM manual_reviews;
DELETE FROM essays;
DELETE FROM pending_submissions;
DELETE FROM assignment_reports;
COMMIT;
VACUUM;
"@
$sql | & sqlite3 $db

# 如存在自增序列表则重置（可选）
$hasSeq = & sqlite3 $db "SELECT EXISTS(SELECT 1 FROM sqlite_master WHERE name='sqlite_sequence');"
if ($hasSeq -eq 1) {
  & sqlite3 $db "DELETE FROM sqlite_sequence WHERE name IN ('manual_reviews','essays','pending_submissions','assignment_reports');"
}
