chrome.runtime.onInstalled.addListener(() => {
    console.log('OpenOperator extension installed.');
});

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'getHistory') {
        chrome.storage.local.get(['llmHistory'], (result) => {
            sendResponse({ history: result.llmHistory || [] });
        });
        return true; // Will respond asynchronously
    }
});

chrome.storage.onChanged.addListener((changes, area) => {
    if (area === 'local' && changes.llmHistory) {
        // Notify all tabs about the history update
        chrome.tabs.query({}, (tabs) => {
            tabs.forEach(tab => {
                chrome.tabs.sendMessage(tab.id, { 
                    action: 'historyUpdated',
                    history: changes.llmHistory.newValue 
                }).catch(() => {
                    // Ignore errors for inactive tabs
                });
            });
        });
    }
});