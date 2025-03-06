document.addEventListener('DOMContentLoaded', async () => {
    chrome.storage.local.get(['mistralApiKey'], (result) => {
        if (!result.mistralApiKey) {
            promptForApiKey();
        }
    });
    loadHistory();
});

function promptForApiKey() {
    const userApiKey = prompt('Please enter your Mistral API key:');
    if (userApiKey) {
        chrome.storage.local.set({ mistralApiKey: userApiKey }, () => {
            console.log('API key saved.');
        });
    } else {
        alert('API key is required to use this extension.');
    }
}


// Settings button handler
document.getElementById('settings').addEventListener('click', () => {
    promptForApiKey();
});

async function getCurrentTabHTML() {
    try {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        const result = await chrome.scripting.executeScript({
            target: { tabId: tab.id },
            function: () => {
                // Clean the HTML content to remove scripts and unnecessary elements
                const clone = document.documentElement.cloneNode(true);
                const scripts = clone.getElementsByTagName('script');
                while (scripts[0]) {
                    scripts[0].parentNode.removeChild(scripts[0]);
                }
                return {
                    title: document.title,
                    url: window.location.href,
                    html: clone.outerHTML // Include full HTML
                };
            }
        });
        return result[0].result;
    } catch (error) {
        console.error('Error getting page content:', error);
        throw error;
    }
}

async function stitchScreenshots(screenshots) {
    try {
        // Create canvas
        const canvas = document.createElement('canvas');
        const firstImage = await loadImage(screenshots[0].image);
        
        canvas.width = firstImage.width;
        canvas.height = window.innerHeight * screenshots.length;
        
        const ctx = canvas.getContext('2d');

        // Draw each screenshot onto the canvas
        for (let i = 0; i < screenshots.length; i++) {
            const img = await loadImage(screenshots[i].image);
            ctx.drawImage(img, 0, i * window.innerHeight);
        }

        // Save the final image
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
        const filename = `fullpage-${timestamp}.png`;
        
        const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/png'));
        const url = URL.createObjectURL(blob);
        
        await chrome.downloads.download({
            url: url,
            filename: filename,
            saveAs: false
        });

        document.getElementById('response').textContent = 'Screenshot captured and saved!';
    } catch (error) {
        console.error('Error stitching screenshots:', error);
        document.getElementById('response').textContent = `Error: ${error.message}`;
    }
}

async function captureFullPageScreenshot() {
    try {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        const screenshots = [];

        // Get page dimensions first
        const dimensions = await chrome.scripting.executeScript({
            target: { tabId: tab.id },
            function: () => ({
                height: Math.max(
                    document.documentElement.scrollHeight,
                    document.body.scrollHeight
                ),
                viewportHeight: window.innerHeight
            })
        });

        const { height, viewportHeight } = dimensions[0].result;
        const totalScreenshots = Math.ceil(height / viewportHeight);

        // Create canvas for final image
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');

        // Set up message listener for screenshots
        chrome.runtime.onMessage.addListener(async function messageHandler(message) {
            if (message.type === 'takeScreenshot') {
                // Take screenshot at current scroll position
                const screenshot = await chrome.tabs.captureVisibleTab(null, { format: 'png' });
                screenshots.push({
                    image: screenshot,
                    position: message.currentPosition
                });

                // Update progress
                document.getElementById('response').textContent = 
                    `Capturing screenshot ${screenshots.length} of ${totalScreenshots}...`;

                // If we have all screenshots, stitch them together
                if (screenshots.length === totalScreenshots) {
                    // Remove the message listener
                    chrome.runtime.onMessage.removeListener(messageHandler);
                    
                    // Load first image to get dimensions
                    const firstImage = await loadImage(screenshots[0].image);
                    canvas.width = firstImage.width;
                    canvas.height = height;

                    // Draw all screenshots onto canvas
                    for (const shot of screenshots) {
                        const img = await loadImage(shot.image);
                        ctx.drawImage(img, 0, shot.position);
                    }

                    // Save the final image
                    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
                    const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/png'));
                    const url = URL.createObjectURL(blob);

                    await chrome.downloads.download({
                        url: url,
                        filename: `fullpage-${timestamp}.png`,
                        saveAs: false
                    });

                    document.getElementById('response').textContent = 'Screenshot captured and saved!';
                }
            }
        });

        // Start the scrolling process
        await chrome.scripting.executeScript({
            target: { tabId: tab.id },
            files: ['content.js']
        });

        // Tell content script to start scrolling
        chrome.tabs.sendMessage(tab.id, { action: 'startScrolling' });

    } catch (error) {
        console.error('Error:', error);
        document.getElementById('response').textContent = `Error: ${error.message}`;
    }
}

// Helper function to load images
function loadImage(src) {
    return new Promise((resolve, reject) => {
        const img = new Image();
        img.onload = () => resolve(img);
        img.onerror = reject;
        img.src = src;
    });
}
async function saveToHistory(prompt, response) {
    return new Promise((resolve, reject) => {
        chrome.storage.local.get(['llmHistory'], (result) => {
            const history = result.llmHistory || [];
            const entry = {
                prompt: prompt,
                response: response,
                timestamp: new Date().toISOString()
            };
            
            // Add new entry at the beginning of the array
            history.unshift(entry);
            
            // Keep only the last 100 entries
            const trimmedHistory = history.slice(0, 100);
            
            chrome.storage.local.set({ llmHistory: trimmedHistory }, () => {
                if (chrome.runtime.lastError) {
                    console.error('Error saving to history:', chrome.runtime.lastError);
                    reject(chrome.runtime.lastError);
                } else {
                    // Alert the full history after saving
                    alert('History updated:\n' + JSON.stringify(trimmedHistory, null, 2));
                    resolve();
                }
            });
        });
    });
}

// Add click handler for scan button
document.getElementById('scanPage').addEventListener('click', captureFullPageScreenshot);

// Function to analyze page content
async function analyzePage(pageData, screenshot) {
    const prompt = `Analyze this webpage and provide specific recommendations for what the user might want to do next.

Page Title: ${pageData.title}
URL: ${pageData.url}

Full HTML Content:
${pageData.html}

Please provide:
1. A brief summary of what this page is about (2-3 sentences)
2. 3-5 specific recommendations for what the user might want to do next
3. Any potential actions that would be helpful on this page`;

    try {
        const apiKeyResult = await new Promise((resolve) => {
            chrome.storage.local.get(['mistralApiKey'], (result) => {
                resolve(result.mistralApiKey);
            });
        });

        if (!apiKeyResult) {
            throw new Error('API key not found');
        }

        const response = await fetch('https://api.mistral.ai/v1/chat/completions', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'Authorization': `Bearer ${apiKeyResult}`
            },
            body: JSON.stringify({
                model: 'pixtral-large-latest',
                messages: [{ role: 'user', content: prompt }]
            })
        });

        if (!response.ok) {
            throw new Error(`API error: ${response.status}`);
        }

        const data = await response.json();
        return data.choices[0].message.content;
    } catch (error) {
        console.error('Error:', error);
        throw error;
    }
}

// Function to handle send action (common for button click and Enter key)
async function handleSendAction() {
    const prompt = document.getElementById('prompt').value;
    if (!prompt) {
        alert('Please enter a prompt.');
        return;
    }

    const responseElement = document.getElementById('response');
    responseElement.textContent = 'Processing...';

    try {
        const apiKey = await new Promise((resolve) => {
            chrome.storage.local.get(['mistralApiKey'], (result) => {
                resolve(result.mistralApiKey);
            });
        });

        if (!apiKey) {
            throw new Error('API key not found');
        }

        const llmPrompt = `You are a helpful assistant. Based on the user's instruction, create a JSON plan for the next action. Respond **ONLY** with the JSON object enclosed between <START_JSON> and <END_JSON> tags.


User Instruction: ${prompt}


JSON Format:
{
    "action": "URL change" | "button_click" | "input_text",
    "details": {
        // For "URL change":
        "url": "https://example.com"

        // For "button_click":
        "selector": "#submit-button"

        // For "input_text":
        "selector": "#username",
        "text": "user_input"
    }
}

Ensure there is no additional text outside the <START_JSON> and <END_JSON> tags.`;

        const response = await fetch('https://api.mistral.ai/v1/chat/completions', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'Authorization': `Bearer ${apiKey}`
            },
            body: JSON.stringify({
                model: 'pixtral-large-latest',
                messages: [{ role: 'user', content: llmPrompt }]
            })
        });

        if (!response.ok) {
            throw new Error(`API error: ${response.status} ${response.statusText}`);
        }

        const data = await response.json();
        const planText = data.choices[0].message.content.trim();

        console.log('Raw LLM Response:', planText); // Logging the raw response

        // Attempt to extract JSON from the response
        const startMarker = '<START_JSON>';
        const endMarker = '<END_JSON>';
        const start = planText.indexOf(startMarker);
        const end = planText.indexOf(endMarker);

        if (start === -1 || end === -1) {
            throw new Error('Response does not contain the expected JSON markers.');
        }

        const jsonString = planText.substring(start + startMarker.length, end).trim();

        let plan;
       
        try {
            plan = JSON.parse(jsonString);
        } catch (parseError) {
            console.error('JSON Parsing Error:', parseError);
            alert('Failed to parse the LLM response as JSON. Please ensure the prompt yields a valid JSON.');
            responseElement.textContent = `Error: ${parseError.message}`;
            return;
        }

        // Validate the plan structure
        if (!plan.action || !plan.details) {
            throw new Error('Invalid plan structure received from LLM.');
        }

        // Prepare confirmation message
        let confirmationMessage = `Planned Action: ${plan.action}\n`;
        switch (plan.action) {
            case 'URL change':
                confirmationMessage += `New URL: ${plan.details.url}`;
                break;
            case 'button_click':
                confirmationMessage += `Selector: ${plan.details.selector}`;
                break;
            case 'input_text':
                confirmationMessage += `Selector: ${plan.details.selector}\nText: ${plan.details.text}`;
                break;
            default:
                throw new Error('Unknown action type received.');
        }

        // Ask for user confirmation
        const userConfirmed = confirm(`The following action will be executed:\n\n${confirmationMessage}\n\nDo you want to proceed?`);

        if (userConfirmed) {
            // Send the plan to the content script for execution
            const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
            chrome.tabs.sendMessage(tab.id, { action: 'executePlan', plan: plan }, async (response) => {
                if (chrome.runtime.lastError) {
                    console.error(chrome.runtime.lastError.message);
                    responseElement.textContent = `Error: ${chrome.runtime.lastError.message}`;
                } else if (response && response.status === 'success') {
                    responseElement.textContent = 'Plan executed successfully.';
                    await saveToHistory(prompt, plan);
                    chrome.tabs.sendMessage(tab.id, { action: 'updateHistory' });

                } else {
                    responseElement.textContent = `Error: ${response.message || 'Unknown error.'}`;
                    
                }
            });

            // Save the prompt and response to history
        
        } else {
            responseElement.textContent = 'Action canceled by the user.';
        }

    } catch (error) {
        console.error('Error:', error);
        responseElement.textContent = `Error: ${error.message}`;
    }
}

// Add click handler for send button
document.getElementById('send').addEventListener('click', async () => {
    await handleSendAction();
});

// Add event listener for Enter key in the prompt textarea
document.getElementById('prompt').addEventListener('keydown', async (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault(); // Prevent adding a new line
        await handleSendAction();
    }
});
// Function to handle send action (common for button click and Enter key)
async function handleSendAction() {
    const prompt = document.getElementById('prompt').value;
    if (!prompt) {
        alert('Please enter a prompt.');
        return;
    }

    const responseElement = document.getElementById('response');
    responseElement.textContent = 'Processing...';

    try {
        const apiKey = localStorage.getItem('mistralApiKey');
        if (!apiKey) {
            throw new Error('API key not found');
        }

        const llmPrompt = `You are a helpful assistant. Based on the user's instruction, create a JSON plan for the next action. Respond **ONLY** with the JSON object enclosed between <START_JSON> and <END_JSON> tags.

User Instruction: ${prompt}

JSON Format:
{
    "action": "URL change" | "button_click" | "input_text",
    "details": {
        // For "URL change":
        "url": "https://example.com"

        // For "button_click":
        "selector": "#submit-button"

        // For "input_text":
        "selector": "#username",
        "text": "user_input"
    }
}

Ensure there is no additional text outside the <START_JSON> and <END_JSON> tags.
`;

        const response = await fetch('https://api.mistral.ai/v1/chat/completions', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'Authorization': `Bearer ${apiKey}`
            },
            body: JSON.stringify({
                model: 'pixtral-large-latest',
                messages: [{ role: 'user', content: llmPrompt }]
            })
        });

        if (!response.ok) {
            throw new Error(`API error: ${response.status} ${response.statusText}`);
        }

        const data = await response.json();
        const planText = data.choices[0].message.content.trim();

        console.log('Raw LLM Response:', planText); // Logging the raw response

        // Attempt to extract JSON from the response
       // Attempt to extract JSON from the response
        const startMarker = '<START_JSON>';
        const endMarker = '<END_JSON>';
        const start = planText.indexOf(startMarker);
        const end = planText.indexOf(endMarker);

        if (start === -1 || end === -1) {
            throw new Error('Response does not contain the expected JSON markers.');
        }

        const jsonString = planText.substring(start + startMarker.length, end).trim();

        let plan;
        try {
            plan = JSON.parse(jsonString);
        } catch (parseError) {
            console.error('JSON Parsing Error:', parseError);
            alert('Failed to parse the LLM response as JSON. Please ensure the prompt yields a valid JSON.');
            responseElement.textContent = `Error: ${parseError.message}`;
            return;
        }

        // Validate the plan structure
        if (!plan.action || !plan.details) {
            throw new Error('Invalid plan structure received from LLM.');
        }

        // Prepare confirmation message
        let confirmationMessage = `Planned Action: ${plan.action}\n`;
        switch (plan.action) {
            case 'URL change':
                confirmationMessage += `New URL: ${plan.details.url}`;
                break;
            case 'button_click':
                confirmationMessage += `Selector: ${plan.details.selector}`;
                break;
            case 'input_text':
                confirmationMessage += `Selector: ${plan.details.selector}\nText: ${plan.details.text}`;
                break;
            default:
                throw new Error('Unknown action type received.');
        }

        // Ask for user confirmation
        const userConfirmed = confirm(`The following action will be executed:\n\n${confirmationMessage}\n\nDo you want to proceed?`);

        if (userConfirmed) {
            // Send the plan to the content script for execution
            const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
            chrome.tabs.sendMessage(tab.id, { action: 'executePlan', plan: plan }, (response) => {
                if (chrome.runtime.lastError) {
                    console.error(chrome.runtime.lastError.message);
                    responseElement.textContent = `Error: ${chrome.runtime.lastError.message}`;
                } else if (response && response.status === 'success') {
                    responseElement.textContent = 'Plan executed successfully.';
                } else {
                    responseElement.textContent = `Error: ${response.message || 'Unknown error.'}`;
                }
            });

            // Save the prompt and response to history
            saveToHistory(prompt, plan);
        } else {
            responseElement.textContent = 'Action canceled by the user.';
        }

    } catch (error) {
        console.error('Error:', error);
        responseElement.textContent = `Error: ${error.message}`;
    }
}


// Function to load history (for potential future use in popup.js)
function loadHistory() {
    chrome.storage.local.get(['llmHistory'], (result) => {
        // This function can be expanded if you want to display history within popup.html
        // Currently, history is handled via the sidebar in content.js
    });
}

document.getElementById('clearHistory').addEventListener('click', () => {
    if (confirm('Are you sure you want to clear all history?')) {
        chrome.storage.local.set({ llmHistory: [] }, () => {
            // Notify all tabs about the history update
            chrome.tabs.query({}, (tabs) => {
                tabs.forEach(tab => {
                    chrome.tabs.sendMessage(tab.id, { 
                        action: 'historyUpdated',
                        history: []
                    }).catch(() => {
                        // Ignore errors for inactive tabs
                    });
                });
            });
        });
    }
});