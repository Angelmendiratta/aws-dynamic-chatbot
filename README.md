# aws-dynamic-chatbot

An AI-powered dual-assistant chatbot built using **AWS Lex V2, AWS Lambda, API Gateway, HTML, CSS, and JavaScript**.

The chatbot supports two business workflows:

- **Consultation Assistant** – Handles service requests, maintenance bookings, and appointment scheduling.
- **Sales Assistant** – Assists customers with product inquiries and purchase consultations.

Users can either chat naturally using Amazon Lex or complete a dynamic in-chat consultation form generated entirely by AWS Lambda.

---

# Design Principle

> **The backend controls the workflow. The frontend only renders it.**

All business logic lives inside the AWS Lambda functions.

The frontend is only responsible for:

- Rendering the chat interface
- Displaying dynamic forms
- Sending user input to the backend
- Displaying responses returned by the backend

Any change to:

- Form fields
- Labels
- Validation rules
- Product lists
- Appointment dates
- Time slots
- Booking workflow

is made inside the Lambda functions—not in the frontend.

---

# Architecture

![Architecture](docs/architecture.png)

---

# AWS Request Flow

![AWS Flow](docs/screenshots/aws_flow.png)

---

# System Architecture

```
                User
                  │
                  ▼
     HTML / CSS / JavaScript Frontend
                  │
                  ▼
          Amazon API Gateway
                  │
                  ▼
          Router Lambda
      (apihandler_lambda.py)
                  │
        ┌─────────┴─────────┐
        ▼                   ▼
Consultation Lambda     Sales Lambda
                  │
                  ▼
             Amazon Lex V2
                  │
                  ▼
           Response to Frontend
```

---

# Features

- Dual AI assistants
- Dynamic consultation forms
- Real-time form validation
- AWS Lex conversational chatbot
- AWS Lambda backend
- Amazon API Gateway integration
- Appointment booking workflow
- Session management
- Responsive web interface

---

# Repository Structure

```
integrated-chatbot/
│
├── backend/
│   ├── lambda_functions/
│   │   ├── consultation_handler.py
│   │   └── sales_handler.py
│   │
│   ├── router/
│   │   └── apihandler_lambda.py
│   │
│   └── requirements.txt
│
├── frontend/
│   ├── index.html
│   ├── script.js
│   └── style.css
│
├── docs/
│   ├── architecture.png
│   └── screenshots/
│       └── aws_flow.png
│
├── .gitignore
└── README.md
```

---

# Backend Components

## Router Lambda

**backend/router/apihandler_lambda.py**

Acts as the central router for every incoming request.

Responsibilities:

- Receives requests from API Gateway
- Determines the active assistant
- Routes dynamic form requests
- Invokes the appropriate Lambda
- Forwards conversational messages to Amazon Lex
- Returns responses to the frontend

---

## Consultation Handler

**backend/lambda_functions/consultation_handler.py**

Responsible for:

- Building consultation forms
- Form validation
- Appointment scheduling
- Booking confirmation
- Consultation workflow

---

## Sales Handler

**backend/lambda_functions/sales_handler.py**

Responsible for:

- Product consultation workflow
- Dynamic sales forms
- Validation
- Lead generation
- Purchase consultation workflow

---

# Frontend Components

## index.html

Provides the chatbot interface.

---

## style.css

Contains all styling for:

- Chat interface
- Dynamic forms
- Buttons
- Responsive layout

---

## script.js

Handles:

- Chat rendering
- Dynamic form rendering
- API communication
- Session management
- User interactions
- Form workflow

---

# Request Flow

### Dynamic Form Flow

```
User
   │
   ▼
Frontend
   │
   ▼
API Gateway
   │
   ▼
Router Lambda
   │
   ▼
Business Lambda
   │
   ▼
Generate Form Schema
   │
   ▼
Frontend Renders Form
   │
User Completes Form
   │
   ▼
Backend Validation
   │
   ▼
Booking Confirmation
```

---

### Chat Flow

```
User Message

↓

Frontend

↓

API Gateway

↓

Router Lambda

↓

Amazon Lex

↓

Lambda Fulfillment

↓

Frontend Response
```

---

# Tech Stack

### Frontend

- HTML5
- CSS3
- JavaScript

### Backend

- Python

### AWS Services

- Amazon Lex V2
- AWS Lambda
- Amazon API Gateway
- AWS IAM
- Amazon CloudWatch

### Tools

- Git
- GitHub
- GitHub Codespaces
- VS Code

---

# Local Development

Clone the repository

```bash
git clone https://github.com/Angelmendiratta/aws-dynamic-chatbot.git
```

Install backend dependencies

```bash
cd backend
pip install -r requirements.txt
```

Configure the API endpoint inside:

```
frontend/script.js
```

Replace

```javascript
const API_URL = "YOUR_API_GATEWAY_URL_HERE";
```

with your deployed API Gateway endpoint.

Open:

```
frontend/index.html
```

to run the frontend locally.

---

# AWS Deployment

Deploy:

- Router Lambda
- Consultation Lambda
- Sales Lambda

Create an HTTP API Gateway endpoint and connect it to the Router Lambda.

Configure:

- Amazon Lex Bot
- Lambda permissions
- IAM roles
- Environment variables

Finally update the API endpoint inside:

```
frontend/script.js
```

---

# Screenshots

## Architecture

![Architecture](docs/architecture.png)

## AWS Request Flow

![AWS Flow](docs/screenshots/aws_flow.png)

---

# Future Improvements

- Authentication
- Database integration (Amazon DynamoDB)
- Email notifications
- Analytics dashboard
- Admin portal
- Multi-language support
- Additional AI assistants

---

# Author

**Angel Mendiratta**

AI Software Developer | AWS | Python | JavaScript | Amazon Lex | AWS Lambda