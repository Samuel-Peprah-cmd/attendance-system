// Handles all POST requests to the Main Backend
const ScannerAPI = {
    async sendScan(payload, apiUrl, deviceKey) { // 🚩 Change 'token' to 'payload'
        try {
            const response = await fetch(`${apiUrl}/api/scanner/scan`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Device-Key': deviceKey
                },
                // 🚩 Send the whole object { qr_token, lat, lng }
                body: JSON.stringify(payload) 
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.message || 'System Error');
            }

            return await response.json();
        } catch (error) {
            console.error("API Error:", error);
            throw error;
        }
    }
};

// // Handles all POST requests to the Main Backend
// const ScannerAPI = {
//     async sendScan(token, apiUrl, deviceKey) {
//         try {
//             const response = await fetch(`${apiUrl}/api/scanner/scan`, {
//                 method: 'POST',
//                 headers: {
//                     'Content-Type': 'application/json',
//                     'X-Device-Key': deviceKey
//                 },
//                 body: JSON.stringify({ qr_token: token })
//             });

//             if (!response.ok) {
//                 const errorData = await response.json();
//                 throw new Error(errorData.message || 'System Error');
//             }

//             return await response.json();
//         } catch (error) {
//             console.error("API Error:", error);
//             throw error;
//         }
//     }
// };