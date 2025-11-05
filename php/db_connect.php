<?php
// db_connect.php
// Enhanced DB connector with connection pooling and retry logic
// Tries MySQL using environment variables (DB_HOST, DB_NAME, DB_USER, DB_PASS).
// Falls back to an on-disk SQLite database at ../backend/passengers.db.

// Connection pool storage
class ConnectionPool {
    private static $instances = [];
    private static $maxPoolSize = 10;
    private static $timeout = 5; // seconds
    
    public static function getInstance($dsn, $user = null, $pass = null) {
        $key = md5($dsn . $user);
        if (!isset(self::$instances[$key])) {
            if (count(self::$instances) >= self::$maxPoolSize) {
                // Remove oldest connection if pool is full
                array_shift(self::$instances);
            }
            self::$instances[$key] = self::createConnection($dsn, $user, $pass);
        }
        return self::$instances[$key];
    }
    
    private static function createConnection($dsn, $user, $pass) {
        $retries = 3;
        $lastError = null;
        
        while ($retries > 0) {
            try {
                $options = [
                    PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
                    PDO::ATTR_TIMEOUT => self::$timeout,
                    PDO::ATTR_PERSISTENT => true
                ];
                
                $pdo = new PDO($dsn, $user, $pass, $options);
                return $pdo;
            } catch (PDOException $e) {
                $lastError = $e;
                $retries--;
                if ($retries > 0) {
                    error_log("Database connection failed, retrying... Error: " . $e->getMessage());
                    sleep(1); // Wait before retry
                }
            }
        }
        
        throw new Exception("Failed to connect to database after 3 attempts. Last error: " . $lastError->getMessage());
    }
}

function get_db_connection() {
    // Try MySQL if env vars are present
    $mysqlHost = getenv('DB_HOST');
    $mysqlName = getenv('DB_NAME');
    $mysqlUser = getenv('DB_USER');
    $mysqlPass = getenv('DB_PASS');

    if ($mysqlHost && $mysqlName && $mysqlUser !== false) {
        try {
            // Add connection timeout and other parameters to DSN
            $dsn = sprintf(
                'mysql:host=%s;dbname=%s;charset=utf8mb4;connect_timeout=5;wait_timeout=28800',
                $mysqlHost,
                $mysqlName
            );
            
            // Get connection from pool
            $pdo = ConnectionPool::getInstance($dsn, $mysqlUser, $mysqlPass);
            
            // Verify connection is still alive
            $pdo->query('SELECT 1');
            
            return $pdo;
        } catch (PDOException $e) {
            $errorInfo = [
                'error' => $e->getMessage(),
                'code' => $e->getCode(),
                'trace' => $e->getTraceAsString()
            ];
            error_log('MySQL connection error: ' . json_encode($errorInfo));
            // fall through to sqlite
        }
    }

    // Fallback to SQLite stored next to backend
    $sqliteFile = __DIR__ . DIRECTORY_SEPARATOR . '..' . DIRECTORY_SEPARATOR . 'backend' . DIRECTORY_SEPARATOR . 'passengers.db';
    try {
        // Ensure directory exists
        $dir = dirname($sqliteFile);
        if (!is_dir($dir)) {
            @mkdir($dir, 0755, true);
        }
        $pdo = new PDO('sqlite:' . $sqliteFile);
        $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
        // Create a passengers table if it doesn't exist (simple schema)
        $pdo->exec("CREATE TABLE IF NOT EXISTS passengers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            passport TEXT,
            flight TEXT,
            seat INTEGER
        )");
        return $pdo;
    } catch (PDOException $e) {
        error_log('SQLite connection failed: ' . $e->getMessage());
        return null;
    }
}

?>