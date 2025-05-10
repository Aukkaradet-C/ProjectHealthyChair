<?php
require_once 'connectDB.php';
$conn->query("UPDATE user_session_tb SET is_active = 0 WHERE is_active = 1");
echo json_encode(["status" => "cleared"]);
?>
