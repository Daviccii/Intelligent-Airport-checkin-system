<?php
// Set security headers
header("X-Content-Type-Options: nosniff");
header("X-Frame-Options: DENY");
header("X-XSS-Protection: 1; mode=block");
header("Content-Security-Policy: default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'");
header("Strict-Transport-Security: max-age=31536000; includeSubDomains");

require_once __DIR__ . '/db_connect.php';

// Initialize error handling
set_error_handler(function($errno, $errstr, $errfile, $errline) {
    error_log("Error ($errno): $errstr in $errfile on line $errline");
    return false;
});

// boardingpass.php?passport=XXXXX
$passport = isset($_GET['passport']) ? trim($_GET['passport']) : '';
if (!$passport) {
    http_response_code(400);
    echo "Missing 'passport' parameter";
    exit;
}

// Try reading passengers.json first (lightweight for your Python backend)
$passengersFile = realpath(__DIR__ . '/../backend/passengers.json');
$passenger = null;
if ($passengersFile && file_exists($passengersFile)) {
    try {
        $raw = file_get_contents($passengersFile);
        if ($raw === false) {
            throw new Exception("Failed to read passengers.json");
        }
        
        $list = json_decode($raw, true);
        if (json_last_error() !== JSON_ERROR_NONE) {
            throw new Exception("JSON decode error: " . json_last_error_msg());
        }
        
        if (!is_array($list)) {
            throw new Exception("Invalid JSON structure: expected array");
        }
        
        foreach ($list as $p) {
            if (isset($p['passport']) && $p['passport'] === $passport) {
                $passenger = $p;
                // Also fetch flight details from flights.json
                $flightsFile = realpath(__DIR__ . '/../backend/flights.json');
                if ($flightsFile && file_exists($flightsFile)) {
                    $flightsRaw = file_get_contents($flightsFile);
                    $flights = json_decode($flightsRaw, true);
                    if (is_array($flights)) {
                        foreach ($flights as $f) {
                            if ($f['flight_number'] === $p['flight']) {
                                $passenger['gate'] = $f['gate'] ?? 'TBA';
                                $passenger['departure_time'] = $f['departure_time'] ?? 'TBA';
                                break;
                            }
                        }
                    }
                }
                break;
            }
        }
    } catch (Exception $e) {
        error_log("Error processing JSON: " . $e->getMessage());
        // Continue to DB as fallback
    }
}

// If not found, try the DB connector
if (!$passenger) {
    $pdo = get_db_connection();
    if ($pdo) {
        try {
            $stmt = $pdo->prepare('SELECT name, passport, flight, seat FROM passengers WHERE passport = :passport LIMIT 1');
            $stmt->execute([':passport' => $passport]);
            $row = $stmt->fetch(PDO::FETCH_ASSOC);
            if ($row) {
                $passenger = $row;
            }
        } catch (Exception $e) {
            error_log('DB lookup failed: ' . $e->getMessage());
        }
    }
}

if (!$passenger) {
    http_response_code(404);
    echo "Passenger not found";
    exit;
}

function h($s) { return htmlspecialchars($s, ENT_QUOTES|ENT_SUBSTITUTE, 'UTF-8'); }
?>
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Boarding Pass - <?= h($passenger['name']) ?></title>
  <link rel="stylesheet" href="/style.css">
  <style> .bp {max-width:720px;margin:28px auto;padding:18px;background:#fff;border-radius:12px;box-shadow:0 8px 24px rgba(0,0,0,0.06)} .bp h2{margin:0 0 14px} </style>
</head>
<body>
  <div class="container">
    <div class="bp">
      <h2>Boarding Pass</h2>
      <div style="display:flex;justify-content:space-between;align-items:start">
        <div>
          <p><strong>Name:</strong> <?= h($passenger['name']) ?></p>
          <p><strong>Passport:</strong> <?= h($passenger['passport']) ?></p>
          <p><strong>Flight:</strong> <?= h($passenger['flight']) ?></p>
          <p><strong>Seat:</strong> <?= h($passenger['seat']) ?></p>
          <p><strong>Gate:</strong> <?= h($passenger['gate'] ?? 'TBA') ?></p>
          <p><strong>Departure:</strong> <?= h($passenger['departure_time'] ?? 'TBA') ?></p>
          <p style="margin-top:12px"><a href="/checkin">Back to check-in</a></p>
        </div>
        <div>
          <?php
          // Generate QR code data
          $qrData = json_encode([
              'passport' => $passenger['passport'],
              'flight' => $passenger['flight'],
              'seat' => $passenger['seat'],
              'name' => $passenger['name'],
              'gate' => $passenger['gate'] ?? 'TBA',
              'departure' => $passenger['departure_time'] ?? 'TBA'
          ]);
          // Generate data URI for QR code
          $qrUrl = 'https://chart.googleapis.com/chart?' . http_build_query([
              'cht' => 'qr',
              'chs' => '200x200',
              'chl' => urlencode($qrData)
          ]);
          ?>
          <img src="<?= h($qrUrl) ?>" alt="Boarding Pass QR Code" style="width:200px;height:200px;margin:10px;">
        </div>
      </div>
    </div>
  </div>
</body>
</html>