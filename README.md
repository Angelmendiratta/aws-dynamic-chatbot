AWS Dynamic Chatbot
    
An AI-powered dual-assistant chatbot built on AWS. It combines Amazon Lex V2 conversational AI with dynamic in-chat forms generated serverlessly via AWS Lambda. The entire business logic lives in the backend - the frontend simply renders what it’s told.
________________________________________
Features
Feature	Description
Dual AI Assistants	Consultation Assistant & Sales Assistant, each with its own workflow
Dynamic Forms	In-chat consultation forms built and validated entirely by Lambda
Natural Language	Full Amazon Lex V2 conversational chatbot support
Backend-Driven Workflow	Change forms, validation, products, or slots without touching the frontend
Responsive UI	Clean, mobile-friendly chat interface
Serverless	100% serverless AWS architecture
________________________________________
Architecture
+-------------+
|    User     |
+------+------+
       |
       v
+-----------------------------+
|  HTML / CSS / JS Frontend   |
|  (Renders only - no logic)  |
+-------------+---------------+
              |
              v
+-----------------------------+
|      API Gateway (HTTP)     |
+-------------+---------------+
              |
              v
+-----------------------------+
|       Router Lambda         |
|    (apihandler_lambda.py)   |
+-------------+---------------+
       |---------|
       v         v
+------------+ +------------+
|Consultation| |   Sales    |
|  Lambda    | |  Lambda    |
+------+-----+ +------+-----+
       |              |
       +------+-------+
              |
              v
+-----------------------------+
|       Amazon Lex V2         |
|   (NLU + Intent Handling)   |
+-----------------------------+
Request Flows
Dynamic Form Flow
User -> Frontend -> API Gateway -> Router Lambda -> Business Lambda
                                                        |
                                              Generate Form Schema
                                                        |
User <- Frontend <- Rendered Form <--------------------+
  |
Submit Form -> Backend Validation -> Booking Confirmation
Chat Flow
User Message -> Frontend -> API Gateway -> Router Lambda -> Amazon Lex
                                                              |
User <- Frontend <- Response <------------------ Lambda Fulfillment
________________________________________
Repository Structure
aws-dynamic-chatbot/
|
|-- backend/
|   |-- lambda_functions/
|   |   |-- consultation_handler.py   # Consultation form & booking logic
|   |   |-- sales_handler.py        # Sales inquiry & lead logic
|   |
|   |-- router/
|   |   |-- apihandler_lambda.py    # Central request router
|   |
|   |-- requirements.txt
|
|-- frontend/
|   |-- index.html                  # Chatbot UI
|   |-- style.css                   # Styling & responsive layout
|   |-- script.js                   # Rendering, API calls, session mgmt
|
|-- docs/
|   |-- architecture.png
|   |-- screenshots/
|   |   |-- aws_flow.png
|
|-- .gitignore
|-- README.md
________________________________________
Tech Stack
Layer	Technology
Frontend	HTML5, CSS3, Vanilla JavaScript
Backend	Python 3.9+
AI/NLP	Amazon Lex V2
Compute	AWS Lambda
API	Amazon API Gateway (HTTP API)
Security	AWS IAM
Observability	Amazon CloudWatch
Dev Tools	Git, GitHub, VS Code
________________________________________
Getting Started
Prerequisites
•	AWS Account
•	AWS CLI configured
•	Python 3.9+
•	A deployed Amazon Lex V2 bot
1. Clone the Repository
git clone https://github.com/Angelmendiratta/aws-dynamic-chatbot.git
cd aws-dynamic-chatbot
2. Install Backend Dependencies
cd backend
pip install -r requirements.txt
3. Deploy AWS Resources
1.	Create Lambda Functions
–	Deploy apihandler_lambda.py as the Router Lambda
–	Deploy consultation_handler.py as the Consultation Lambda
–	Deploy sales_handler.py as the Sales Lambda
2.	Set up API Gateway
–	Create an HTTP API
–	Add a POST / route
–	Integrate with the Router Lambda
3.	Configure Amazon Lex V2
–	Create your bot with intents for both assistants
–	Attach Lambda fulfillment hooks
4.	IAM & Permissions
–	Grant API Gateway permission to invoke Router Lambda
–	Grant Router Lambda permission to invoke Consultation & Sales Lambdas
–	Grant Lambdas permission to call Lex V2
4. Configure the Frontend
Open frontend/script.js and update the API endpoint:
const API_URL = "https://your-api-gateway-id.execute-api.region.amazonaws.com";
5. Run Locally
Simply open frontend/index.html in your browser - no build step required.
________________________________________
Design Principle
The backend controls the workflow. The frontend only renders it.
All business logic - form fields, labels, validation rules, product lists, appointment slots, booking workflows - lives inside AWS Lambda. The frontend is a thin rendering layer:
•	Renders chat interface
•	Displays dynamic forms
•	Sends input to backend
•	Displays responses
Want to change a form field? Edit the Lambda.
Want to add a new product? Edit the Lambda.
Want to change validation? Edit the Lambda.
The frontend never needs to change.
________________________________________
Screenshots
Add screenshots of your chatbot in action to docs/screenshots/ and embed them here:
![Chat Interface](docs/screenshots/chat-interface.png)
![Dynamic Form](docs/screenshots/dynamic-form.png)
________________________________________
Future Roadmap
•	☐ Authentication - Cognito user login
•	☐ Database - Amazon DynamoDB for persistent bookings
•	☐ Notifications - Amazon SES/SNS email confirmations
•	☐ Analytics - CloudWatch dashboards & usage metrics
•	☐ Admin Portal - Web UI for managing forms & workflows
•	☐ Multi-language - Lex built-in language support
•	☐ Additional Assistants - Support, billing, etc.
________________________________________
Author
Angel Mendiratta
AI Software Developer | AWS | Python | JavaScript | Amazon Lex | AWS Lambda
 
________________________________________
License
This project is open-source. Feel free to fork, modify, and deploy!
