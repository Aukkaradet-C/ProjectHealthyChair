<?php
require_once 'connectDB.php'; // ใช้ไฟล์เชื่อม DB
$data = json_decode(file_get_contents("php://input"), true);
$user_id = $data["user_id"] ?? null;

if ($user_id) {
    $stmt = $conn->prepare("REPLACE INTO user_session_tb (user_id, is_active) VALUES (?, 1)");
    $stmt->bind_param("i", $user_id);
    $stmt->execute();
    echo json_encode(["status" => "ok", "user_id" => $user_id]);
} else {
    echo json_encode(["status" => "error", "message" => "Missing user_id"]);
}
?>
