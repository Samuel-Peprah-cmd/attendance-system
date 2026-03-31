const SoundService = {
    playSuccess() {
        new Audio('/static/sounds/success.mp3').play().catch(e => console.log("Audio blocked"));
    },
    playError() {
        new Audio('/static/sounds/error.mp3').play().catch(e => console.log("Audio blocked"));
    }
};