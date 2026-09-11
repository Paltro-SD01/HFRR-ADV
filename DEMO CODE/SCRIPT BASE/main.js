const { app, BrowserWindow } = require('electron');
const path = require('path');

function createWindow() {
    const mainWindow = new BrowserWindow({
        width: 1450,
        height: 900,
        backgroundColor: '#09090b',
        title: "HFRR Adv Diagnostics Master Control Engine",
        webPreferences: {
            nodeIntegration: true,
            contextIsolation: false
        }
    });

    // Strip generic browser dropdown navigational menu tools
    mainWindow.setMenuBarVisibility(false);
    mainWindow.loadFile('index.html');
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') app.quit();
});