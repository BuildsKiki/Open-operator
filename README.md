# Open-operator Chrome Extension

## Overview

Open-operator is a Chrome extension designed to enhance your browsing experience by integrating with various APIs to provide additional functionalities. This extension allows users to interact with different AI models and services directly from their browser.

## Features

- **API Key Management**: Securely store and manage API keys for different services.
- **Integration with AI Models**: Connect with AI models like OpenAI, Mistral, and others to perform tasks such as text completion, data retrieval, and more.
- **User-Friendly Interface**: Easy-to-use interface for managing settings and preferences.

## Installation

1. **Prepare Environment Variables**:
   - Create a `.env` file in the root directory of the extension.
   - Define the necessary API keys in the `.env` file. Here are the keys you need to set:
     ```plaintext
     NGROK_AUTH_TOKEN=your_ngrok_auth_token
     E2B_API_KEY=your_e2b_api_key
     MISTRAL_API_KEY=your_mistral_api_key
     ```
   - Ensure you replace `your_ngrok_auth_token`, `your_e2b_api_key`, and `your_mistral_api_key` with your actual API keys.

2. **Load the Extension in Chrome**:
   - Open Chrome and navigate to `chrome://extensions/`.
   - Enable "Developer mode" by toggling the switch in the top right corner.
   - Click on "Load unpacked" and select the directory where the extension files are located.

## Usage

1. **Prompt for API Key**:
   - Upon installation, the extension will prompt you to enter your Mistral API key if not already set in the `.env` file.
   - The key is stored locally using Chrome's storage API for secure access.
   - Reference: 
     ```javascript:popup.js
     startLine: 2
     endLine: 10
     ```

2. **Configure Settings**:
   - Access the settings page to configure additional options such as API endpoints and model preferences.

3. **Interact with AI Models**:
   - Use the extension to send requests to AI models and receive responses directly in your browser.

## Security

- API keys are stored securely using Chrome's local storage.
- Ensure that your API keys are kept confidential and not shared with unauthorized users.

## Contributing

We welcome contributions from the community. If you would like to contribute, please fork the repository and submit a pull request.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more details.

## Contact

For any questions or support, please contact [your-email@example.com](mailto:your-email@example.com).