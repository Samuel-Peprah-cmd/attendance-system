/**
 * ATOMDEV | Universal Web Terminal Logic
 * Handles: Activation, Camera Lifecycle, and Auto-Reset on De-authorization
 */

let html5QrcodeScanner;
let currentFacingMode = "environment"; // Default to back camera for better focus
let DEVICE_KEY =
    localStorage.getItem('atom_device_key') ||
    localStorage.getItem('device_key') ||
    localStorage.getItem('deviceKey');

// 🚩 GLOBAL GPS CACHE (Keeps the satellite link "warm")
let activeCoords = { lat: null, lng: null, timestamp: 0 };

function getStoredSchoolId() {
    return (
        localStorage.getItem('device_school_id') ||
        localStorage.getItem('school_id') ||
        localStorage.getItem('terminal_school_id') ||
        ''
    );
}

if (navigator.geolocation) {
    navigator.geolocation.watchPosition(
        (pos) => {
            activeCoords = {
                lat: pos.coords.latitude,
                lng: pos.coords.longitude,
                timestamp: Date.now()
            };
            console.log("📍 GPS Sync: Precision Lock Updated.");
        },
        (err) => console.warn("GPS Background Error:", err.message),
        { enableHighAccuracy: true, maximumAge: 5000, timeout: 10000 }
    );
}
/**
 * 1. INITIALIZATION
 * Checks if the device is already "Married" to a school.
 */
// function checkActivation() {
//     const setupOverlay = document.getElementById('setup-overlay');
    
//     if (!DEVICE_KEY) {
//         // Show the Activation Screen if no key is stored
//         setupOverlay.classList.remove('hidden');
//         console.log("📟 Terminal Status: Awaiting Activation...");
//     } else {
//         // Start the scanner immediately if we have a key
//         setupOverlay.classList.add('hidden');
//         startScanner();
//     }
// }

function checkActivation() {
    const setupOverlay = document.getElementById('setup-overlay');
    const schoolId = getStoredSchoolId();

    if (!DEVICE_KEY || !schoolId) {
        setupOverlay.classList.remove('hidden');
        console.log("📟 Terminal Status: Awaiting Activation...");
    } else {
        setupOverlay.classList.add('hidden');
        startScanner();
    }
}

/**
 * 2. ACTIVATION LOGIC
 * Verifies the key with the Master Server and saves it locally.
 */
// async function activateDevice() {
//     const inputKey = document.getElementById('setup-key-input').value.trim();
//     // const apiUrl = document.getElementById('api-config').dataset.url;
//     const apiUrl = window.location.origin;

//     if (!inputKey) {
//         alert("Please enter a valid API Key.");
//         return;
//     }

//     try {
//         // Ping the backend to verify this key exists and is active
//         const response = await fetch(`${apiUrl}/api/scanner/ping`, {
//             method: 'GET',
//             headers: { 
//                 'X-Device-Key': inputKey,
//                 'ngrok-skip-browser-warning': 'true', // 🚩 NGROK BYPASS
//                 'Content-Type': 'application/json'
//              }
//         });
        
//         if (response.ok) {
//             const data = await response.json();
//             // SAVE TO BROWSER MEMORY
//             localStorage.setItem('atom_device_key', inputKey);
//             DEVICE_KEY = inputKey;
            
//             console.log(`✅ Activation Success: Connected to ${data.school}`);
//             location.reload(); // Refresh to initialize the camera with the new key
//         } else {
//             const errorData = await response.json();
//             alert(`❌ Activation Failed: ${errorData.message || "Invalid Key"}`);
//         }
//     } catch (e) {
//         console.error("Connection Error:", e);
//         alert("🔌 Server Unreachable: Ensure the backend is running and CORS is enabled.");
//     }
// }

async function activateDevice() {
    const inputKey = document.getElementById('setup-key-input').value.trim();
    const apiUrl = window.location.origin;

    if (!inputKey) {
        alert("Please enter a valid API Key.");
        return;
    }

    try {
        const response = await fetch(`${apiUrl}/api/scanner/ping`, {
            method: 'GET',
            headers: {
                'X-Device-Key': inputKey,
                'ngrok-skip-browser-warning': 'true',
                'Content-Type': 'application/json'
            }
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.message || "Invalid Key");
        }

        const schoolId =
            data.school_id ||
            data.schoolId ||
            (data.school && data.school.id) ||
            null;

        if (!schoolId) {
            throw new Error("Activation succeeded, but school ID was not returned by the server.");
        }

        // Save device key in all expected formats
        localStorage.setItem('atom_device_key', inputKey);
        localStorage.setItem('device_key', inputKey);
        localStorage.setItem('deviceKey', inputKey);

        // Save school identity for scanner unlock
        localStorage.setItem('device_school_id', String(schoolId));
        localStorage.setItem('school_id', String(schoolId));
        localStorage.setItem('terminal_school_id', String(schoolId));

        // Optional school display name
        if (data.school_name) {
            localStorage.setItem('school_name', data.school_name);
        } else if (typeof data.school === 'string') {
            localStorage.setItem('school_name', data.school);
        }

        DEVICE_KEY = inputKey;

        console.log(`✅ Activation Success: Connected to ${data.school_name || data.school || schoolId}`);
        location.reload();

    } catch (e) {
        console.error("Connection Error:", e);
        alert(`❌ Activation Failed: ${e.message || "Server Unreachable"}`);
    }
}

/**
 * 3. SCANNER ENGINE
 * Manages the camera feed and QR detection.
 */
function startScanner() {
    if (html5QrcodeScanner) {
        html5QrcodeScanner.clear();
    }

    html5QrcodeScanner = new Html5QrcodeScanner(
        "reader", 
        { 
            fps: 30, 
            qrbox: { width: 280, height: 280 },
            aspectRatio: 1.0,
            formatsToSupport: [ Html5QrcodeSupportedFormats.QR_CODE ],
            videoConstraints: {
                facingMode: currentFacingMode, 
                width: { min: 640, ideal: 1280 },
                height: { min: 480, ideal: 720 }
            }
        }
    );
    html5QrcodeScanner.render(onScanSuccess, onScanFailure);
    
    // Update the UI to show which Node is active
    document.getElementById('node-display').innerText = `Node: ${DEVICE_KEY.substring(0, 8)}...`;
}


async function onScanSuccess(decodedText) {
    console.log("🎯 QR Detected:", decodedText); 
    
    // 1. Instant Pause & UI Feedback
    if (html5QrcodeScanner) html5QrcodeScanner.pause();
    const apiUrl = window.location.origin;

    // 2. Grab Cached GPS (No waiting!)
    // We check if the GPS data is "Fresh" (less than 2 minutes old)
    const isFresh = (Date.now() - activeCoords.timestamp) < 120000;
    
    const payload = {
        qr_token: decodedText,
        lat: isFresh ? activeCoords.lat : null,
        lng: isFresh ? activeCoords.lng : null
    };

    // 🚩 ADD THIS LINE TO DEBUG YOUR PHONE'S GPS
    console.log(`📡 SENDING GPS: Lat ${payload.lat}, Lng ${payload.lng}`);

    try {
        // 3. Background Send
        const data = await ScannerAPI.sendScan(payload, apiUrl, DEVICE_KEY);
        
        // 4. Update UI with Student Data
        showResult(data);
        SoundService.playSuccess();

    } catch (error) {
        console.error("❌ Scan Error:", error.message);
        if (error.message.includes("401")) {
            handleDeauthorization();
        } else {
            showError(error.message);
            SoundService.playError();
            // Show alert on phone so guard knows why it failed
            alert("Error: " + error.message);
        }
    }

    // 5. Fast-Reset (2 seconds) to keep the line moving
    setTimeout(() => {
        resetUI();
        if (html5QrcodeScanner) html5QrcodeScanner.resume();
    }, 2000);
}

/**
 * 5. SECURITY UTILITIES
 */
// function handleDeauthorization() {
//     console.warn("⚠️ Device De-authorized. Wiping local memory...");
//     localStorage.removeItem('atom_device_key');
//     alert("This terminal has been de-authorized or reassigned by the Master Admin.");
//     location.reload(); // This will trigger the Setup Overlay
// }

function handleDeauthorization() {
    console.warn("⚠️ Device De-authorized. Wiping local memory...");

    localStorage.removeItem('atom_device_key');
    localStorage.removeItem('device_key');
    localStorage.removeItem('deviceKey');

    localStorage.removeItem('device_school_id');
    localStorage.removeItem('school_id');
    localStorage.removeItem('terminal_school_id');
    localStorage.removeItem('school_name');

    alert("This terminal has been de-authorized or reassigned by the Master Admin.");
    location.reload();
}

// function resetActivation() {
//     if(confirm("Deregister this device? You will need the API key to reconnect.")) {
//         localStorage.removeItem('atom_device_key');
//         location.reload();
//     }
// }

function resetActivation() {
    if (confirm("Deregister this device? You will need the API key to reconnect.")) {
        localStorage.removeItem('atom_device_key');
        localStorage.removeItem('device_key');
        localStorage.removeItem('deviceKey');

        localStorage.removeItem('device_school_id');
        localStorage.removeItem('school_id');
        localStorage.removeItem('terminal_school_id');
        localStorage.removeItem('school_name');

        location.reload();
    }
}


function showResult(data) {
    document.getElementById('idle-view').classList.add('hidden');
    document.getElementById('active-view').classList.remove('hidden');
    
    // 1. Get the Name
    const displayName = data.name || "Unknown Identity";
    
    // 2. Get the Class or Role (display_info)
    // If it's empty, we use "Access Granted" as a last resort
    let displayClass = data.display_info || "Access Granted";

    // 3. Set the Photo
    document.getElementById('student-img').src = data.photo_url || '/static/img/default_avatar.png';

    // 4. Update the Text in HTML
    document.getElementById('student-name').innerText = displayName;
    document.getElementById('student-class').innerText = displayClass; // 🚩 Now shows Class or Role
    document.getElementById('scan-time').innerText = data.timestamp || new Date().toLocaleTimeString();
    
    // 5. Update the Badge
    const direction = data.direction || "IN";
    const badge = document.getElementById('status-badge');
    badge.innerText = `CHECKED ${direction}`;
    
    // Dynamic Colors
    let badgeColor = "bg-green-500";
    if (direction === 'OUT') badgeColor = "bg-orange-500";
    if (data.status === 'BREACH') badgeColor = "bg-red-600 animate-pulse";

    badge.className = `absolute -bottom-5 left-1/2 -translate-x-1/2 px-10 py-4 rounded-2xl text-[11px] font-black text-white shadow-2xl uppercase tracking-[0.3em] whitespace-nowrap ${badgeColor}`;
}

function resetUI() {
    document.getElementById('idle-view').classList.remove('hidden');
    document.getElementById('active-view').classList.add('hidden');
}

function showError(message) {
    // Optional: show a red toast or alert
    console.error("Displaying UI Error:", message);
}

function onScanFailure(error) {
    // Silent fail for every frame without a QR code
}

function switchCamera() {
    currentFacingMode = (currentFacingMode === "user") ? "environment" : "user";
    startScanner();
}

// 📦 The Offline Queue
let offlineQueue = JSON.parse(localStorage.getItem('offlineScans')) || [];

function sendScan(qrToken) {
    const scanData = {
        qr_token: qrToken,
        timestamp: Date.now() / 1000 // Send the exact moment of the scan
    };

    fetch('/api/scanner/scan', {
        method: 'POST',
        headers: { 
            'Content-Type': 'application/json',
            'X-Device-Key': 'YOUR_DEVICE_KEY' 
        },
        body: JSON.stringify(scanData)
    })
    .then(response => {
        if (!response.ok) throw new Error('Network offline');
        showSuccessUI(); // Flash the student's face
    })
    .catch(error => {
        // 📴 Save to Offline Queue if network fails
        offlineQueue.push(scanData);
        localStorage.setItem('offlineScans', JSON.stringify(offlineQueue));
        showOfflineWarning(); // Show "Saved Offline" on the web page
    });
}

// 🔄 Auto-Sync Loop (Checks every 30 seconds)
setInterval(() => {
    if (offlineQueue.length > 0 && navigator.onLine) {
        console.log("Syncing offline scans...");
        const nextScan = offlineQueue[0];
        
        // Try to upload the first item
        fetch('/api/scanner/scan', { /* same fetch as above */ })
        .then(res => {
            if(res.ok) {
                offlineQueue.shift(); // Remove from queue
                localStorage.setItem('offlineScans', JSON.stringify(offlineQueue));
            }
        });
    }
}, 30000);


// Start the lifecycle on Page Load
window.onload = checkActivation;