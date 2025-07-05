# AI-Medical-Diagnosis-System

AI Medical Diagnosis System
An AI-powered medical diagnosis system that uses Bayesian Networks, Natural Language Processing (NLP), and a Neo4j graph database to predict diseases based on observed symptoms. The system provides real-time diagnosis and flags unusual symptom combinations as special cases.

Features
Bayesian Network: Implements a probabilistic reasoning model using pgmpy to infer disease likelihoods based on symptoms.

Neo4j Knowledge Graph: Stores and queries disease-symptom relationships in a graph database for efficient retrieval.

Natural Language Processing (NLP): Uses spaCy to extract diseases and symptoms from text and populate the knowledge graph.

Real-Time Diagnosis: Users input symptoms and get real-time disease predictions along with associated probabilities.

Special Case Detection: Flags unusual symptom combinations and stores them as special cases for future reference.

Technologies Used
Python: The core programming language for implementing the system.

pgmpy: Used for building and querying the Bayesian Network.

Neo4j: A graph database for storing and querying the disease-symptom relationships.

spaCy: An NLP library for extracting entities (diseases and symptoms) from text.

JSON: Used for storing symptom probabilities and other data structures.

Setup Instructions
1. Clone the Repository
bash
Copy
Edit
git clone https://github.com/<your-username>/AI-Medical-Diagnosis-System.git
cd AI-Medical-Diagnosis-System
2. Install Dependencies
Make sure you have Python 3.x installed. Then, install the necessary Python packages using pip:

bash
Copy
Edit
pip install -r requirements.txt
The requirements.txt file includes:

pgmpy (for Bayesian Network)

neo4j (for connecting to Neo4j)

spaCy (for NLP tasks)

json (for storing data)

3. Install Neo4j
Download and install Neo4j from neo4j.com.

Start your Neo4j instance and create a database for this project.

4. Set Up Neo4j Database Connection
Make sure to update the Neo4j connection details (URI, username, password) in the settings.py file with your own credentials:

python
Copy
Edit
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "password"
5. Load the Knowledge Base
Before using the system, you need to load a knowledge base of diseases and symptoms. Place your knowledge.txt file (or create your own) in the project directory and run:

bash
Copy
Edit
python load_knowledge.py
This will populate the Neo4j database with diseases, symptoms, and their relationships.

Usage
Running the System
To start the system, run the main script:

bash
Copy
Edit
python main.py
You will be prompted to:

Load the knowledge file into the Neo4j database (first-time setup).

Diagnose a patient by inputting symptoms and receiving disease predictions along with probabilities.

View audit logs (Admin only).

Interactive Diagnosis
Enter the patient's name.

List the symptoms (comma-separated).

Choose the match mode (e.g., match all symptoms, partial match, etc.).

Get disease predictions with probabilities, based on the provided symptoms.

If symptoms are unusual, the system flags them as a special case.

Example
Here is an example of how the system works:

🔍 Checking Neo4j connection...
✅  Neo4j connected (RETURN 1 ⇒ 1)
✅ Neo4j connection verified!
Name: Harry
Welcome, Harry

🎉 Welcome, Harry!

==================================================
     MEDICAL DIAGNOSIS SYSTEM
==================================================
1) Load knowledge.txt into Neo4j
2) Diagnose patient
3) View last 10 audit events (Admin only)
4) Exit
==================================================
Enter your choice (1-4): 3

🔐 Admin access required...
Enter admin password: 12345
✅ Admin access granted

📊 AUDIT LOG - Last 10 Events:
--------------------------------------------------
1751703231384  USER_LOGIN  → Harry
1751615348784  USER_LOGIN  → affan
1751609722696  USER_LOGIN  → faizan
1751609382502  USER_LOGIN  → faizan
1751609207853  USER_LOGIN  → ga
1751608619607  USER_LOGIN  → ba
1751607980388  UPSERT_SPECIAL_CASE_WITH_PATIENT
1751607962663  USER_LOGIN  → faizan
1751606511405  UPSERT_SPECIAL_CASE_WITH_PATIENT
1751606495567  USER_LOGIN  → Affan

==================================================
     MEDICAL DIAGNOSIS SYSTEM
==================================================
1) Load knowledge.txt into Neo4j
2) Diagnose patient
3) View last 10 audit events (Admin only)
4) Exit
==================================================
Enter your choice (1-4): 2

🏥 Entering diagnosis mode...
Patient name: john
List present symptoms comma-sep: Cough, Wheezing, Fever, Rash

📊 Symptom-Disease Probabilities:

Cough:
  Flu: 20.0%
  COVID-19: 12.0%
  Pneumonia: 12.0%
  Asthma: 12.0%
  Influenza: 12.0%
  Bronchitis: 12.0%
  Tuberculosis: 10.0%
  Lung Cancer: 10.0%

Wheezing:
  Asthma: 100.0%

Fever:
  Flu: 20.4%
  Malaria: 15.3%
  Typhoid: 15.3%
  COVID-19: 12.2%
  Dengue: 12.2%
  Pneumonia: 12.2%
  Influenza: 12.2%

Rash:
  Dengue: 100.0%

Match mode – (a)ll symptoms, (p)artial ≥2, (w)ide ≥1  [a]: p

🏥 Diseases in KG matching criteria: ['Flu', 'COVID-19', 'Dengue', 'Pneumonia', 'Influenza', 'Asthma']
Contributing
Feel free to fork this repository, make improvements, and submit pull requests. If you find any bugs or have suggestions, please open an issue.

License
This project is open-source and available under the MIT License.

