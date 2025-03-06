import os
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from mistralai import Mistral
from datetime import datetime
import re
from e2b import Sandbox

# Load environment variables
load_dotenv()

# Get environment variables
E2B_API_KEY = os.getenv('E2B_API_KEY')
MISTRAL_API_KEY = os.getenv('MISTRAL_API_KEY')

# Initialize Flask app
app = Flask(__name__)
port = 8000

# Configure clients
client = Mistral(api_key=MISTRAL_API_KEY)

def ensure_directory_exists(sandbox, path):
    result = sandbox.commands.run(f'mkdir -p {os.path.dirname(path)}')
    if result.exit_code != 0:
        raise Exception(f"Failed to create directory: {result.stderr}")
    
    # List directory contents for debugging
    result = sandbox.commands.run(f'ls -la {os.path.dirname(path)}')
    print(f"Directory contents: {result.stdout}")

@app.route('/execute', methods=['POST'])
def execute_code():
    try:
        # Initialize sandbox
        sandbox = Sandbox()
        print('Sandbox created', sandbox.sandbox_id)
        
        # Initialize timeline events list
        timeline_events = []
        
        # RESPONSE INITIALIZATION
        response = {
            'status': 'success',
            'timeline_events': [],
            'sandbox_id': sandbox.sandbox_id,
            'generated_files': []
        }

        # Handle file upload
        if 'python_file' not in request.files:
            raise ValueError("No Python file uploaded")
        
        python_file = request.files['python_file']
        if not python_file.filename.endswith('.py'):
            raise ValueError("Invalid file type. Must be a .py file")
        
        # Read and store Python file
        python_code = python_file.read().decode('utf-8')
        sandbox.files.write('script.py', python_code)
        
        # Verify file was written
        result = sandbox.commands.run('cat script.py')
        print(f"File contents: {result.stdout}")
        
        timeline_events.append({
            "step": "File Upload",
            "status": "complete",
            "details": f"Uploaded Python file: {python_file.filename}",
            "color": "blue",
            "input": python_code,
            "output": result.stdout,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        })
        
        # Upload data files if present
        data_files = request.files.getlist('data_files')
        uploaded_data_files = []
        if data_files:
            sandbox.commands.run('mkdir -p data')
            for data_file in data_files:
                remote_path = f'data/{data_file.filename}'
                sandbox.files.write(remote_path, data_file.read())
                uploaded_data_files.append(remote_path)
            
            # List uploaded files for verification
            result = sandbox.commands.run('ls -la data')
            
            timeline_events.append({
                "step": "Data Upload",
                "status": "complete",
                "details": f"Uploaded data files: {', '.join([f.filename for f in data_files]) if data_files else 'No data files'}",
                "color": "purple",
                "input": str([f.filename for f in data_files]) if data_files else "No files",
                "output": result.stdout if data_files else "No files uploaded",
                "timestamp": datetime.now().strftime("%H:%M:%S")
            })
        
        # Install dependencies
        dependencies = ['pandas', 'numpy', 'matplotlib', 'scikit-learn', 'seaborn', 'requests']
        install_command = 'pip install ' + ' '.join(dependencies) + ' --quiet'
        result = sandbox.commands.run(install_command)
        print("Installation output:", result.stdout)
        
        # Verify installations
        verify_result = sandbox.commands.run('pip list | grep -E "pandas|numpy|matplotlib|scikit-learn|seaborn|requests"')
        
        timeline_events.append({
            "step": "Dependencies",
            "status": "complete",
            "details": "Installed required packages",
            "color": "orange",
            "input": install_command,
            "output": verify_result.stdout or "Installation completed silently",
            "timestamp": datetime.now().strftime("%H:%M:%S")
        })
        
        # Optimize code
        system_prompt = """You are an expert Python programmer. Analyze and optimize the provided Python code for:
        1. Better performance
        2. Better readability
        3. Better error handling
        4. Better data validation
        5. Better visualization if applicable
        6. Include all dependancies that may be missing as part of the dependancy install step (e.g pip install)
        
        Return only the optimized Python code without any markdown formatting, code blocks, or explanations."""

        mistral_response = client.chat.complete(
            model="mistral-large-latest",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": python_code}
            ]
        )

        optimized_code = mistral_response.choices[0].message.content.strip()
        optimized_code = re.sub(r'^```python\s*', '', optimized_code)
        optimized_code = re.sub(r'\s*```$', '', optimized_code)
        optimized_code = optimized_code.strip()
        
        # Write optimized code to root directory
        sandbox.files.write('optimized_script.py', optimized_code)
        
        # Verify file was written
        result = sandbox.commands.run('cat optimized_script.py')
        print(f"Optimized file contents: {result.stdout}")
        result = sandbox.commands.run('ls -la .')
        print("Directory contents before execution:", result.stdout)
        
        timeline_events.append({
            "step": "Code Optimization",
            "status": "complete",
            "details": "Code optimized successfully",
            "color": "yellow",
            "input": python_code,
            "output": optimized_code,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        })
        
        # Execute the optimized script
        result = sandbox.commands.run('python optimized_script.py')
        print("Execution output:", result.stdout)
        
        # Check for generated files in root directory
        generated_files = []
        try:
            result = sandbox.commands.run('ls -la .')
            print("Directory contents after execution:", result.stdout)
            
            for line in result.stdout.split('\n'):
                if any(line.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.pdf']):
                    filename = line.split()[-1]
                    file_content = sandbox.files.read(f'{filename}')
                    generated_files.append({
                        'name': filename,
                        'content': file_content
                    })
        except Exception as e:
            print(f"Error checking for generated files: {str(e)}")
        
        timeline_events.append({
            "step": "Execution",
            "status": "complete",
            "details": "Code executed successfully",
            "color": "teal",
            "input": "Running optimized script",
            "output": result.stdout,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        })
        
        # Close the sandbox since we're done
        sandbox.close()
        
        # Aggregate all timeline events
        response['timeline_events'] = timeline_events
        response['generated_files'] = generated_files
        response['python_code'] = python_code
        response['optimized_code'] = optimized_code
        response['output'] = result.stdout
        
        return jsonify(response)
    
    except Exception as e:
        print(f"Error in execute_code: {str(e)}")
        if 'sandbox' in locals():
            try:
                sandbox.close()
            except:
                pass
        return jsonify({
            'status': 'error',
            'message': str(e),
            'timeline_events': [{
                "step": "Execution",
                "status": "error",
                "details": f"Error during execution: {str(e)}",
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "color": "red",
                "input": "Error occurred during processing",
                "output": str(e)
            }]
        }), 500

pattern = re.compile(r'```python\n(.*?)\n```', re.DOTALL)

@app.route('/kill-sandboxes', methods=['POST'])
def kill_sandboxes():
    try:
        # Get list of all running sandboxes
        running_sandboxes = Sandbox.list()
        killed_count = 0
        failed_count = 0
        error_messages = []
        
        # Kill each sandbox
        for sandbox_info in running_sandboxes:
            try:
                sandbox = Sandbox(sandbox_info.sandbox_id)
                sandbox.kill()
                killed_count += 1
            except Exception as e:
                failed_count += 1
                error_messages.append(f"Failed to kill sandbox {sandbox_info.sandbox_id}: {str(e)}")
                print(f"Error killing sandbox: {str(e)}")  # Add logging
        
        # Prepare response message
        if killed_count > 0 and failed_count == 0:
            message = f"Successfully killed {killed_count} sandboxes"
        elif killed_count > 0 and failed_count > 0:
            message = f"Killed {killed_count} sandboxes, failed to kill {failed_count}"
        elif killed_count == 0 and failed_count > 0:
            message = f"Failed to kill {failed_count} sandboxes"
        else:
            message = "No active sandboxes found"
            
        return jsonify({
            'status': 'success',
            'message': message,
            'killed_count': killed_count,
            'failed_count': failed_count,
            'errors': error_messages
        })
        
    except Exception as e:
        print(f"Error in kill_sandboxes: {str(e)}")  # Add logging
        return jsonify({
            'status': 'error',
            'message': f"Failed to list/kill sandboxes: {str(e)}",
            'errors': [str(e)]
        }), 500

def match_code_block(llm_response):
    match = pattern.search(llm_response)
    if match:
        code = match.group(1)
        return code
    return ""

def install_dependencies(code_interpreter):
    """Install required Python packages in the sandbox"""
    timeline_events = []
    
    required_packages = [
        'pandas',
        'numpy',
        'matplotlib',
        'scikit-learn',
        'seaborn',
        'torch',
        'requests'
    ]
    
    timeline_events.append({
        "step": "Dependencies", 
        "status": "in_progress", 
        "details": f"Installing required packages: {', '.join(required_packages)}",
        "timestamp": datetime.now().strftime("%H:%M:%S")
    })
    
    for package in required_packages:
        try:
            code_interpreter.notebook.exec_cell(f"!pip install {package} --quiet")
        except Exception as e:
            timeline_events.append({
                "step": "Dependencies", 
                "status": "error",
                "details": f"Failed to install {package}: {str(e)}",
                "timestamp": datetime.now().strftime("%H:%M:%S")
            })
            return timeline_events, False
    
    timeline_events.append({
        "step": "Dependencies", 
        "status": "complete",
        "details": "Successfully installed all required packages",
        "timestamp": datetime.now().strftime("%H:%M:%S")
    })
    
    return timeline_events, True

@app.route('/test')
def test_connection():
    try:
        # Send the prompt to Mistral
        system_prompt = "You are a helpful assistant that can execute python code in a Jupyter notebook. Only respond with the code to be executed and nothing else. Strip backticks in code blocks."
        prompt = "Write a simple Python code that prints 'Hello from E2B!' and does a basic math calculation of 2 + 2"
        
        response = client.chat.complete(
            model="mistral-large-latest",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]
        )
        
        # Extract the code from the response
        code = response.choices[0].message.content
        
        with Sandbox() as sandbox:
            execution = sandbox.run_code(code)
            
            return jsonify({
                'status': 'success',
                'response': str(response),
                'message': 'E2B Sandbox is working correctly',
                'test_output': execution.text,
                'logs': execution.logs.stdout if execution.logs else None
            })
            
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': 'E2B Sandbox encountered an error',
            'error': str(e)
        }), 500

@app.route('/')
def openoperator():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>openoperator</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                background-color: #2f3542;
                color: #ffffff;
                margin: 0;
                padding: 20px;
                min-height: 100vh;
            }

            .container {
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
                margin-bottom: 100px;
            }

            h1 {
                font-size: 24px;
                text-align: center;
                margin-bottom: 30px;
                color: #ffffff;
            }

            h3 {
                color: #a4b0be;
                margin-top: 20px;
                margin-bottom: 10px;
            }

            .upload-section {
                background-color: #3a4150;
                padding: 20px;
                border-radius: 8px;
                margin-bottom: 20px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.2);
                border: 1px solid #4a4f5d;
            }

            .file-input {
                display: none;
            }

            .upload-button {
                padding: 12px 20px;
                background-color: #454e63;
                color: white;
                border: 1px solid #4a4f5d;
                cursor: pointer;
                border-radius: 8px;
                transition: background-color 0.2s;
                display: inline-block;
                margin-right: 10px;
                font-size: 14px;
            }

            .upload-button:hover {
                background-color: #576075;
            }

            .upload-button:disabled {
                background-color: #3a4150;
                cursor: not-allowed;
            }

            #fileName {
                color: #a4b0be;
                margin-left: 10px;
                font-size: 14px;
            }

            .results-section {
                background-color: #3a4150;
                padding: 20px;
                border-radius: 8px;
                margin-top: 20px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.2);
                border: 1px solid #4a4f5d;
            }

            .code-display {
                background-color: #2f3542;
                padding: 15px;
                border-radius: 6px;
                margin: 10px 0;
                white-space: pre-wrap;
                overflow-x: auto;
                font-family: 'Courier New', monospace;
                font-size: 14px;
                line-height: 1.5;
                border: 1px solid #4a4f5d;
            }

            .download-button {
                padding: 12px 20px;
                background-color: #27ae60;
                color: white;
                border: none;
                cursor: pointer;
                border-radius: 8px;
                transition: background-color 0.2s;
                margin-top: 15px;
                font-size: 14px;
                display: block;
                width: 100%;
            }

            .download-button:hover {
                background-color: #219a52;
            }

            .form-row {
                display: flex;
                align-items: center;
                margin-bottom: 10px;
            }

            .submit-row {
                margin-top: 15px;
            }

            .loading {
                opacity: 0.7;
                cursor: not-allowed;
            }

            .error-message {
                background-color: #e74c3c;
                color: white;
                padding: 10px;
                border-radius: 6px;
                margin-top: 10px;
                font-size: 14px;
                display: none;
            }

            .success-message {
                background-color: #27ae60;
                color: white;
                padding: 10px;
                border-radius: 6px;
                margin-top: 10px;
                font-size: 14px;
                display: none;
            }

            /* Timeline styles */
            .timeline-container {
                position: fixed;
                bottom: 0;
                left: 0;
                right: 0;
                background: #3a4150;
                padding: 20px;
                border-top: 1px solid #4a4f5d;
                transform: translateY(90%);
                transition: transform 0.3s ease;
                z-index: 1000;
            }

            .timeline-container.expanded {
                transform: translateY(0);
            }

            .timeline-toggle {
                position: absolute;
                top: -30px;
                left: 50%;
                transform: translateX(-50%);
                background: #3a4150;
                border: 1px solid #4a4f5d;
                border-bottom: none;
                padding: 5px 15px;
                border-radius: 8px 8px 0 0;
                cursor: pointer;
                color: #ffffff;
            }

            .timeline-cards {
                display: flex;
                gap: 15px;
                overflow-x: auto;
                padding-bottom: 10px;
            }

            .timeline-card {
                background: #2f3542;
                padding: 15px;
                border-radius: 8px;
                min-width: 200px;
                border: 1px solid #4a4f5d;
                position: relative;
                background: #2f3542 !important;
            }

            .timeline-card.complete {
                border-left: 3px solid #27ae60;
            }

            .timeline-card.error {
                border-left: 3px solid #e74c3c;
            }

            .timeline-card.in_progress {
                border-left: 3px solid #f1c40f;
                animation: pulse 2s infinite;
            }

            .timeline-step {
                font-weight: bold;
                margin-bottom: 5px;
            }

 .timeline-details {
    font-size: 0.9em;
    color: #a4b0be;
    margin-bottom: 15px;
    white-space: pre-wrap;
    font-family: 'Courier New', monospace;
    max-height: 300px;
    overflow-y: auto;
    background: #2f3542;
    padding: 10px;
    border-radius: 4px;
    background: #3a4150 !important;
}

.timeline-card {
    background: #3a4150;
    padding: 15px;
    border-radius: 8px;
    min-width: 300px;
    max-width: 500px;
    border: 1px solid #4a4f5d;
    position: relative;
}

            .timeline-timestamp {
                font-size: 0.8em;
                color: #747d8c;
                position: absolute;
                bottom: 5px;
                right: 10px;
            }

            @keyframes pulse {
                0% { opacity: 1; }
                50% { opacity: 0.6; }
                100% { opacity: 1; }
            }

            ::-webkit-scrollbar {
                width: 8px;
                height: 8px;
            }

            ::-webkit-scrollbar-track {
                background: #2f3542;
                border-radius: 4px;
            }

            ::-webkit-scrollbar-thumb {
                background: #4a4f5d;
                border-radius: 4px;
            }

            ::-webkit-scrollbar-thumb:hover {
                background: #5a6070;
            }
            .timeline-item {
    margin-bottom: 10px;
    border-radius: 4px;
    overflow: hidden;
}

.timeline-header {
    padding: 10px;
    cursor: pointer;
    color: white;
    display: flex;
    justify-content: space-between;
}

.timeline-details {
    padding: 10px;
    background-color: #f5f5f5;
}

.timeline-details.collapsed .expanded-content {
    display: none;
}

.expanded-content {
    padding: 10px;
    background-color: white;
    border-radius: 4px;
    margin-top: 10px;
}

.expanded-content pre {
    background-color: #f8f8f8;
    padding: 10px;
    border-radius: 4px;
    overflow-x: auto;
}
            
.timeline-card[data-step="File Upload"] {
    border-left: 4px solid #2196F3;  /* blue */
}

.timeline-card[data-step="Data Upload"] {
    border-left: 4px solid #9C27B0;  /* purple */
}

.timeline-card[data-step="Dependencies"] {
    border-left: 4px solid #FF9800;  /* orange */
}

.timeline-card[data-step="Code Optimization"] {
    border-left: 4px solid #FDD835;  /* yellow */
}

.timeline-card[data-step="Execution"] {
    border-left: 4px solid #4CAF50;  /* green */
}

/* Add error state */
.timeline-card[data-status="error"] {
    border-left: 4px solid #f44336;  /* red */
}

.timeline-card[data-step="File Upload"] {
    border-left: 4px solid #3B82F6;  /* light blue */
}

.timeline-card[data-step="Data Upload"] {
    border-left: 4px solid #8B5CF6;  /* light purple */
}

.timeline-card[data-step="Dependencies"] {
    border-left: 4px solid #F59E0B;  /* amber */
}

.timeline-card[data-step="Code Optimization"] {
    border-left: 4px solid #FBBF24;  /* yellow */
}

.timeline-card[data-step="Execution"] {
    border-left: 4px solid #10B981;  /* teal */
}

.timeline-card[data-status="error"] {
    border-left: 4px solid #EF4444;  /* red */
}

.timeline-card {
    margin: 10px;
    background: #F9FAFB;  /* light gray */
    border-radius: 4px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    overflow: hidden;
}

.timeline-header {
    padding: 12px 16px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    color: #111827;  /* dark gray */
    cursor: pointer;
    user-select: none;
}

.timeline-content {
    padding: 16px;
}

.timeline-details {
    margin-bottom: 8px;
}

.timeline-expanded {
    border-top: 1px solid #E5E7EB;  /* light border */
    padding-top: 12px;
    margin-top: 12px;
}

.timeline-input h4,
.timeline-output h4 {
    margin: 0 0 8px 0;
    color: #6B7280;  /* medium gray */
}

.timeline-expanded pre {
    background: grey;  /* very light gray */
    padding: 12px;
    border-radius: 4px;
    overflow-x: auto;
    margin: 0;
}

.timeline-timestamp {
    font-size: 0.85em;
    opacity: 0.9;
}

.timeline-header:hover {
    filter: brightness(1.05);
}
   .timeline-card {
        margin: 10px;
        background: #F3F4F6;  /* light grey */
        border-left: 4px solid #D1D5DB;  /* medium grey border */
        border-radius: 4px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        overflow: hidden;
    }

    .timeline-header {
        padding: 12px 16px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        color: #111827;  /* dark grey */
        cursor: pointer;
        user-select: none;
    }

    .timeline-content {
        padding: 16px;
    }

    .timeline-details {
        margin-bottom: 8px;
    }

    .timeline-expanded {
        border-top: 1px solid #E5E7EB;  /* light border */
        padding-top: 12px;
        margin-top: 12px;
    }

    .timeline-input h4,
    .timeline-output h4 {
        margin: 0 0 8px 0;
        color: #6B7280;  /* medium grey */
    }

    .timeline-expanded pre {
        background: grey;  /* very light grey */
        padding: 12px;
        border-radius: 4px;
        overflow-x: auto;
        margin: 0;
    }

    .timeline-timestamp {
        font-size: 0.85em;
        opacity: 0.9;
    }

    .timeline-header:hover {
        filter: brightness(1.05);
    }
        </style>
    </head>
    <body>
       <div class="container">
    <h1>openoperator</h1>
    
    <div class="upload-section">
        <form id="uploadForm" enctype="multipart/form-data">
            <div class="form-row">
                <input type="file" id="fileInput" class="file-input" name="python_file" accept=".py" required>
                <input type="file" id="dataInput" class="file-input" name="data_files" multiple>
                <label for="fileInput" class="upload-button">📁 Select Python File</label>
                <label for="dataInput" class="upload-button">📊 Select Data Files</label>
                <div style="margin-left: 10px;">
                    <div id="fileName" style="color: #a4b0be;"></div>
                    <div id="data-filenames" style="color: #a4b0be;"></div>
                </div>
            </div>
            
            <div class="submit-row">
                <button type="submit" class="upload-button" style="width: 100%;">
                    ⚡ Process and Optimize Code
                </button>
            </div>
            <div class="cleanup-row" style="margin-top: 10px;">
                <button id="killSandboxes" type="button" class="upload-button" style="background-color: #576075;">
                    🗑️ Kill All Sandboxes
                </button>
            </div>
            <div id="errorMessage" class="error-message"></div>
            <div id="successMessage" class="success-message"></div>
        </form>
    </div>

    <div class="results-section" id="results" style="display: none;">
        <h3>Original Code:</h3>
        <div class="code-display" id="originalCode"></div>
        
        <h3>Optimized Code:</h3>
        <div class="code-display" id="optimizedCode"></div>
        
        <h3>Execution Output:</h3>
        <div class="code-display" id="output"></div>
        
        <button class="download-button" id="downloadOptimized">
            💾 Download Optimized Code
        </button>
    </div>
</div>

<div class="timeline-container" id="timelineContainer">
    <button class="timeline-toggle" id="timelineToggle">Show Progress Timeline</button>
    <div class="timeline-cards" id="timelineCards">
        <!-- Timeline cards will be inserted here -->
    </div>
</div>

       <script>
    document.addEventListener('DOMContentLoaded', function() {
        // Initialize elements
        const uploadForm = document.getElementById('uploadForm');
        const fileInput = document.getElementById('fileInput');
        const dataInput = document.getElementById('dataInput');
        const submitButton = document.querySelector('#uploadForm button[type="submit"]');
        const timelineCards = document.getElementById('timelineCards');
        const timelineToggle = document.getElementById('timelineToggle');
        const timelineContainer = document.getElementById('timelineContainer');
        const errorMessage = document.getElementById('errorMessage');
        const successMessage = document.getElementById('successMessage');
        const resultsSection = document.getElementById('results');
        const fileNameSpan = document.getElementById('fileName');
        const dataFilenamesSpan = document.getElementById('data-filenames');

        // File input change handler
        fileInput.addEventListener('change', function(e) {
            if (this.files && this.files[0]) {
                const fileName = this.files[0].name;
                fileNameSpan.textContent = fileName;
                errorMessage.style.display = 'none';
                successMessage.style.display = 'none';
            }
        });

        // Data files input change handler
        dataInput.addEventListener('change', function(e) {
            if (this.files && this.files.length > 0) {
                const fileNames = Array.from(this.files).map(file => file.name).join(', ');
                dataFilenamesSpan.textContent = fileNames;
                errorMessage.style.display = 'none';
                successMessage.style.display = 'none';
            }
        });

        // Timeline toggle handler
        timelineToggle.addEventListener('click', function() {
            const isExpanded = timelineContainer.classList.toggle('expanded');
            this.textContent = isExpanded ? 'Hide Progress Timeline' : 'Show Progress Timeline';
        });

        async function processStep(formData, step = 'start') {
            try {
                // Create a new FormData for this step
                const stepFormData = new FormData();
                
                // Add the current step
                stepFormData.append('step', step);
                
                // Add sandbox_id if we have it
                if (formData.get('sandbox_id')) {
                    stepFormData.append('sandbox_id', formData.get('sandbox_id'));
                }
                
                // Add python_code if we have it
                if (formData.get('python_code')) {
                    stepFormData.append('python_code', formData.get('python_code'));
                }
                
                // Only add files in the start step
                if (step === 'start') {
                    const pythonFile = formData.get('python_file');
                    if (pythonFile) {
                        stepFormData.append('python_file', pythonFile);
                    }
                    const dataFiles = formData.getAll('data_files');
                    dataFiles.forEach(file => {
                        stepFormData.append('data_files', file);
                    });
                }
                
                const response = await fetch('/execute', {
                    method: 'POST',
                    body: stepFormData
                });
                
                const data = await response.json();
                
                if (data.status === 'error') {
                    throw new Error(data.message);
                }

                // Update timeline with the single timeline event
                if (data.timeline_event) {
                    const card = document.createElement('div');
                    card.className = `timeline-card ${data.timeline_event.status}`;
                    card.innerHTML = `
                        <div class="timeline-step">${data.timeline_event.step}</div>
                        <div class="timeline-details">${data.timeline_event.details}</div>
                        <div class="timeline-timestamp">${data.timeline_event.timestamp}</div>
                    `;
                    timelineCards.appendChild(card);
                    timelineCards.scrollLeft = timelineCards.scrollWidth;
                }
                
                // Store important data for next steps
                if (data.sandbox_id) {
                    formData.set('sandbox_id', data.sandbox_id);
                }
                if (data.python_code) {
                    formData.set('python_code', data.python_code);
                    document.getElementById('originalCode').textContent = data.python_code;
                }
                if (data.optimized_code) {
                    formData.set('optimized_code', data.optimized_code);
                    document.getElementById('optimizedCode').textContent = data.optimized_code;
                    resultsSection.style.display = 'block';
                }
                if (data.output) {
                    document.getElementById('output').textContent = data.output;
                }
                
                // Handle generated files
                if (data.generated_files?.length > 0) {
                    const outputDiv = document.getElementById('output');
                    data.generated_files.forEach(file => {
                        const img = document.createElement('img');
                        img.src = `data:image/png;base64,${file.content}`;
                        img.style.maxWidth = '100%';
                        img.style.marginTop = '10px';
                        outputDiv.appendChild(img);
                    });
                }

                if (data.timeline_event) {
                    const card = document.createElement('div');
                    card.className = 'timeline-card';
                    card.setAttribute('data-step', data.timeline_event.step);
                    card.setAttribute('data-status', data.timeline_event.status);
                    
                    card.innerHTML = `
                        <div class="timeline-header" style="background-color: ${data.timeline_event.color}">
                            <div class="timeline-step">${data.timeline_event.step}</div>
                            <div class="timeline-timestamp">${data.timeline_event.timestamp}</div>
                        </div>
                        <div class="timeline-content">
                            <div class="timeline-details">${data.timeline_event.details}</div>
                            <div class="timeline-expanded" style="display: none;">
                                <div class="timeline-input">
                                    <h4>Input:</h4>
                                    <pre><code>${data.timeline_event.input || 'No input'}</code></pre>
                                </div>
                                <div class="timeline-output">
                                    <h4>Output:</h4>
                                    <pre><code>${data.timeline_event.output || 'No output'}</code></pre>
                                </div>
                            </div>
                        </div>
                    `;
                    
                    // Add click handler for expansion
                    card.querySelector('.timeline-header').addEventListener('click', () => {
                        const expanded = card.querySelector('.timeline-expanded');
                        expanded.style.display = expanded.style.display === 'none' ? 'block' : 'none';
                    });
                    
                    timelineCards.appendChild(card);
                    timelineCards.scrollTop = timelineCards.scrollHeight;
                }

                // Handle next step or completion
                if (data.next_step === 'complete') {
                    successMessage.textContent = 'Processing completed successfully!';
                    successMessage.style.display = 'block';
                    submitButton.innerHTML = '⚡ Process and Optimize Code';
                    submitButton.disabled = false;
                    submitButton.classList.remove('loading');
                } else if (data.next_step) {
                    // Wait a short time before starting next step to prevent race conditions
                    await new Promise(resolve => setTimeout(resolve, 100));
                    await processStep(formData, data.next_step);
                }
                
            } catch (error) {
                console.error('Error:', error);
                errorMessage.textContent = error.toString();
                errorMessage.style.display = 'block';
                resultsSection.style.display = 'none';
                submitButton.innerHTML = '⚡ Process and Optimize Code';
                submitButton.disabled = false;
                submitButton.classList.remove('loading');
            }
        }

        // Form submit handler
        uploadForm.addEventListener('submit', async function(e) {
            e.preventDefault(); // Prevent default form submission
            
            // Clear previous results and messages
            timelineCards.innerHTML = '';
            errorMessage.style.display = 'none';
            successMessage.style.display = 'none';
            resultsSection.style.display = 'none';
            
            // Validate file input
            if (!fileInput.files || !fileInput.files[0]) {
                errorMessage.textContent = 'Please select a Python file';
                errorMessage.style.display = 'block';
                return;
            }

            // Disable submit button and show loading state
            submitButton.innerHTML = '⏳ Processing...';
            submitButton.disabled = true;
            submitButton.classList.add('loading');
            
            // Show timeline container
            timelineContainer.classList.add('expanded');
            timelineToggle.textContent = 'Hide Progress Timeline';
            
            // Create initial FormData
            const formData = new FormData();
            formData.append('python_file', fileInput.files[0]);
            if (dataInput.files.length > 0) {
                Array.from(dataInput.files).forEach(file => {
                    formData.append('data_files', file);
                });
            }
            
            try {
                await processStep(formData);
            } catch (error) {
                console.error('Error:', error);
                errorMessage.textContent = error.toString();
                errorMessage.style.display = 'block';
                submitButton.innerHTML = '⚡ Process and Optimize Code';
                submitButton.disabled = false;
                submitButton.classList.remove('loading');
            }
        });

        // Kill sandboxes button handler
        const killSandboxesButton = document.getElementById('killSandboxes');
        killSandboxesButton.addEventListener('click', async function() {
            try {
                this.disabled = true;
                this.innerHTML = '⏳ Cleaning up...';
                
                const response = await fetch('/kill-sandboxes', {
                    method: 'POST'
                });
                const data = await response.json();
                
                if (data.status === 'success') {
                    successMessage.textContent = data.message;
                    successMessage.style.display = 'block';
                } else {
                    throw new Error(data.message);
                }
            } catch (error) {
                errorMessage.textContent = `Failed to kill sandboxes: ${error.message}`;
                errorMessage.style.display = 'block';
            } finally {
                this.disabled = false;
                this.innerHTML = '🗑️ Kill All Sandboxes';
            }
        });

        // Download handler for optimized code
        document.getElementById('downloadOptimized').addEventListener('click', function() {
            const optimizedCode = document.getElementById('optimizedCode').textContent;
            const blob = new Blob([optimizedCode], { type: 'text/plain' });
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'optimized_script.py';
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
        });
    });
    function updateTimeline(event) {
        // Remove any existing card for the current step
        const existingCard = document.querySelector(`.timeline-card[data-step="${event.step}"]`);
        if (existingCard) {
            existingCard.remove();
        }

        // Create a new card for the current step
        const card = document.createElement('div');
        card.className = 'timeline-card';
        card.setAttribute('data-step', event.step);
        card.setAttribute('data-status', event.status);

        card.innerHTML = `
            <div class="timeline-header">
                <div class="timeline-step">${event.step}</div>
                <div class="timeline-timestamp">${event.timestamp}</div>
            </div>
            <div class="timeline-content">
                <div class="timeline-details">${event.details}</div>
                <div class="timeline-expanded" style="display: none;">
                    <div class="timeline-input">
                        <h4>Input:</h4>
                        <pre><code>${event.input || 'No input'}</code></pre>
                    </div>
                    <div class="timeline-output">
                        <h4>Output:</h4>
                        <pre><code>${event.output || 'No output'}</code></pre>
                    </div>
                </div>
            </div>
        `;

        // Add click handler for expansion
        card.querySelector('.timeline-header').addEventListener('click', () => {
            const expanded = card.querySelector('.timeline-expanded');
            expanded.style.display = expanded.style.display === 'none' ? 'block' : 'none';
        });

        // Append the new card to the timeline
        document.querySelector('.timeline').appendChild(card);
        document.querySelector('.timeline').scrollTop = document.querySelector('.timeline').scrollHeight;
    }
</script>
    </body>
    </html>
    '''

if __name__ == "__main__":
    try:
        app.run(port=port)
    except Exception as e:
        print(f"Failed to start server: {str(e)}")
