// Function to sanitize HTML to prevent XSS
function sanitizeHTML(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// Function to create and inject the sidebar
function createSidebar() {
    // Prevent multiple sidebars
    if (document.getElementById('OpenOperator-sidebar')) return;

    const sidebar = document.createElement('div');
    sidebar.id = 'OpenOperator-sidebar';
    sidebar.style.position = 'fixed';
    sidebar.style.top = '0';
    sidebar.style.right = '0'; // Changed to right side
    sidebar.style.width = '300px';
    sidebar.style.height = '100%';
    sidebar.style.backgroundColor = '#2f3542'; // Dark space grey background
    sidebar.style.borderLeft = '1px solid #444'; // Left border instead of right
    sidebar.style.boxShadow = '-2px 0 5px rgba(0,0,0,0.2)'; // Shadow on left side
    sidebar.style.zIndex = '10000';
    sidebar.style.display = 'none';
    sidebar.style.flexDirection = 'column';
    sidebar.style.padding = '15px';
    sidebar.style.overflowY = 'auto';
    sidebar.style.fontFamily = 'Arial, sans-serif';
    sidebar.style.color = '#ffffff'; // Light text color

    // Create header for sidebar
    const header = document.createElement('div');
    header.style.display = 'flex';
    header.style.justifyContent = 'space-between';
    header.style.alignItems = 'center';
    header.style.marginBottom = '15px';
    header.style.padding = '5px 0';

    const title = document.createElement('h2');
    title.textContent = 'OpenOperator History';
    title.style.fontSize = '18px';
    title.style.margin = '0';
    title.style.color = '#ffffff';

    const closeButton = document.createElement('button');
    closeButton.textContent = '✖️';
    closeButton.style.background = 'none';
    closeButton.style.border = 'none';
    closeButton.style.cursor = 'pointer';
    closeButton.style.fontSize = '16px';
    closeButton.style.color = '#ffffff';

    closeButton.addEventListener('click', () => {
        sidebar.style.display = 'none';
        const toggleButton = document.getElementById('OpenOperator-toggle-button');
        if (toggleButton) {
            toggleButton.style.right = '0';
        }
    });

    header.appendChild(title);
    header.appendChild(closeButton);
    sidebar.appendChild(header);

    // Create history container
    const historyContainer = document.createElement('div');
    historyContainer.id = 'OpenOperator-history-container';
    sidebar.appendChild(historyContainer);

    // Append sidebar to body
    document.body.appendChild(sidebar);
}

function loadHistoryIntoSidebar() {
    chrome.runtime.sendMessage({ action: 'getHistory' }, (response) => {
        if (chrome.runtime.lastError) {
            console.error('Error:', chrome.runtime.lastError);
            return;
        }

        const history = response.history || [];
        const historyContainer = document.getElementById('OpenOperator-history-container');
        historyContainer.innerHTML = ''; // Clear existing entries

        if (history.length === 0) {
            historyContainer.textContent = 'No history available.';
            return;
        }

        history.forEach(entry => {
            const entryDiv = document.createElement('div');
            entryDiv.classList.add('history-entry');
            entryDiv.style.marginBottom = '15px';
            entryDiv.style.padding = '12px';
            entryDiv.style.backgroundColor = '#3a4150'; // Darker space grey for entries
            entryDiv.style.border = '1px solid #4a4f5d';
            entryDiv.style.borderRadius = '8px'; // More rounded corners
            entryDiv.style.boxShadow = '0 2px 4px rgba(0,0,0,0.2)';
            entryDiv.style.color = '#ffffff';

            const timestampP = document.createElement('p');
            timestampP.innerHTML = `<em>${new Date(entry.timestamp).toLocaleString()}</em>`;
            timestampP.style.margin = '0 0 8px 0';
            timestampP.style.fontSize = '12px';
            timestampP.style.color = '#a4b0be'; // Lighter grey for timestamp

            const promptP = document.createElement('p');
            promptP.innerHTML = `<strong>Prompt:</strong> ${sanitizeHTML(entry.prompt)}`;
            promptP.style.margin = '0 0 8px 0';
            promptP.style.color = '#ffffff';

            const responseP = document.createElement('p');
            responseP.innerHTML = `<strong>Action:</strong> ${sanitizeHTML(entry.response.action)}<br>
                                 <strong>Details:</strong> <pre style="background-color: #2f3542; padding: 8px; border-radius: 4px;">${sanitizeHTML(JSON.stringify(entry.response.details, null, 2))}</pre>`;
            responseP.style.margin = '0';
            responseP.style.whiteSpace = 'pre-wrap';
            responseP.style.wordBreak = 'break-all';

            entryDiv.appendChild(timestampP);
            entryDiv.appendChild(promptP);
            entryDiv.appendChild(responseP);
            historyContainer.appendChild(entryDiv);
        });
    });
}

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'historyUpdated') {
        console.log('History updated, reloading sidebar');
        loadHistoryIntoSidebar();
    }
    console.log('Received message:', request);
    if (request.action === 'executePlan') {
        const plan = request.plan;
        try {
            switch (plan.action.toLowerCase()) {
                case 'url change':
                    if (plan.details.url) {
                        window.location.href = plan.details.url;
                    } else {
                        throw new Error('URL is missing in the plan.');
                    }
                    break;
                case 'button_click':
                    if (plan.details.selector) {
                        const button = document.querySelector(plan.details.selector);
                        if (button) {
                            button.click();
                        } else {
                            throw new Error(`No element found with selector: ${plan.details.selector}`);
                        }
                    } else {
                        throw new Error('Selector is missing in the plan.');
                    }
                    break;
                case 'input_text':
                    if (plan.details.selector && typeof plan.details.text === 'string') {
                        const input = document.querySelector(plan.details.selector);
                        if (input) {
                            input.value = plan.details.text;
                            input.dispatchEvent(new Event('input', { bubbles: true }));
                        } else {
                            throw new Error(`No input found with selector: ${plan.details.selector}`);
                        }
                    } else {
                        throw new Error('Selector or text is missing in the plan.');
                    }
                    break;
                default:
                    throw new Error(`Unknown action type: ${plan.action}`);
            }
            sendResponse({ status: 'success' });
        } catch (error) {
            console.error('Error executing plan:', error);
            sendResponse({ status: 'error', message: error.message });
        }
        return true;
    } else if (request.action === 'updateHistory') {
        console.log('Updating history in sidebar.');
        loadHistoryIntoSidebar();
    }
});

// Function to create the toggle button
function createToggleButton() {
    if (document.getElementById('OpenOperator-toggle-button')) return;

    const toggleButton = document.createElement('button');
    toggleButton.id = 'OpenOperator-toggle-button';
    toggleButton.textContent = '🗒️';
    toggleButton.style.position = 'fixed';
    toggleButton.style.top = '20px';
    toggleButton.style.right = '0'; // Start at right edge when closed
    toggleButton.style.padding = '8px 12px';
    toggleButton.style.backgroundColor = '#2f3542';
    toggleButton.style.color = '#fff';
    toggleButton.style.border = '1px solid #444';
    toggleButton.style.borderRadius = '8px 0 0 8px'; // Round only left corners
    toggleButton.style.cursor = 'pointer';
    toggleButton.style.zIndex = '10001';
    toggleButton.style.fontSize = '16px';
    toggleButton.style.boxShadow = '-2px 0 5px rgba(0,0,0,0.2)';
    toggleButton.style.transition = 'right 0.3s ease';

    toggleButton.addEventListener('click', () => {
        const sidebar = document.getElementById('OpenOperator-sidebar');
        if (sidebar.style.display === 'none') {
            sidebar.style.display = 'flex';
            toggleButton.style.right = '300px';
            loadHistoryIntoSidebar();
        } else {
            sidebar.style.display = 'none';
            toggleButton.style.right = '0';
        }
    });

    document.body.appendChild(toggleButton);
}

// Initialize the sidebar and toggle button once
createSidebar();
createToggleButton();

// Listen for changes in chrome.storage.local.llmHistory
chrome.storage.onChanged.addListener((changes, area) => {
    if (area === 'local' && changes.llmHistory) {
        const sidebar = document.getElementById('OpenOperator-sidebar');
        if (sidebar.style.display === 'flex') {
            console.log('Detected change in llmHistory. Reloading history.');
            loadHistoryIntoSidebar();
        }
    }
});

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'updateHistory') {
        console.log('Updating history in sidebar.');
        loadHistoryIntoSidebar();
    }
});