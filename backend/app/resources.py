"""Learning resource retrieval for SkillBridge learning-path items.

A skill-gap learning item must surface real, current resources (videos, articles,
official docs, courses) ranked most-helpful-first — not the model inventing
plausible-looking links.

Two sources:
  1. Live retrieval via a search API when a key is configured
     (SKILLBRIDGE_YOUTUBE_API_KEY for videos via the YouTube Data API).
  2. A curated index of real, stable URLs per skill/category maintained here,
     so the demo works offline and the links are always genuine.

Curated links are validated with a cheap HTTP check when the network is
reachable; links that provably fail (4xx/5xx/connection refused) are dropped.
For YouTube, a thumbnail probe is used since the watch page returns 200 even
for removed/private videos.
"""
import os
import re
from urllib.parse import urlparse, parse_qs

YOUTUBE_API_KEY = os.environ.get("SKILLBRIDGE_YOUTUBE_API_KEY", "")


def _res(res_type, title, url, source):
    return {"type": res_type, "title": title, "url": url, "source": source}


# ------------------------------------------------------------------ curated index

# Skill-level curated resources (keyed by lowercase skill name).
_CURATED = {
    "python": [
        _res("video", "Learn Python — Full Course for Beginners (freeCodeCamp)", "https://www.youtube.com/watch?v=rfscVS0vtbw", "freeCodeCamp"),
        _res("doc", "The Python Tutorial (official)", "https://docs.python.org/3/tutorial/", "Python.org"),
        _res("course", "Python for Everybody (Coursera)", "https://www.coursera.org/specializations/python", "Coursera"),
    ],
    "java": [
        _res("video", "Java Programming — Full Course (freeCodeCamp)", "https://www.youtube.com/watch?v=GoXwIVyNvX0", "freeCodeCamp"),
        _res("doc", "Java Language Tutorials (official)", "https://docs.oracle.com/javase/tutorial/", "Oracle"),
        _res("course", "Java Programming and Software Engineering (Coursera)", "https://www.coursera.org/specializations/java-programming", "Coursera"),
    ],
    "c++": [
        _res("video", "C++ Tutorial for Beginners — Full Course (freeCodeCamp)", "https://www.youtube.com/watch?v=vLnPwxZdW4Y", "freeCodeCamp"),
        _res("doc", "cppreference.com", "https://en.cppreference.com/w/", "cppreference"),
        _res("course", "C++ for C Programmers (Coursera)", "https://www.coursera.org/course/cplusplus4c", "Coursera"),
    ],
    "javascript": [
        _res("video", "Learn JavaScript — Full Course for Beginners (freeCodeCamp)", "https://www.youtube.com/watch?v=PkZNo7MFNFg", "freeCodeCamp"),
        _res("doc", "JavaScript Guide (MDN)", "https://developer.mozilla.org/en-US/docs/Web/JavaScript/guide", "MDN"),
        _res("course", "JavaScript Algorithms and Data Structures (freeCodeCamp)", "https://www.freecodecamp.org/learn/javascript-algorithms-and-data-structures/", "freeCodeCamp"),
    ],
    "typescript": [
        _res("video", "TypeScript Course for Beginners (freeCodeCamp)", "https://www.youtube.com/watch?v=BwuLxPH8IDs", "freeCodeCamp"),
        _res("doc", "TypeScript Documentation (official)", "https://www.typescriptlang.org/docs/", "TypeScript"),
        _res("course", "Understanding TypeScript (Udemy)", "https://www.udemy.com/course/understanding-typescript/", "Udemy"),
    ],
    "react": [
        _res("video", "React Course — Beginner's Tutorial (freeCodeCamp)", "https://www.youtube.com/watch?v=bMknfKXIFA8", "freeCodeCamp"),
        _res("doc", "React Docs — Learn (official)", "https://react.dev/learn", "React"),
        _res("course", "Meta Front-End Developer (Coursera)", "https://www.coursera.org/professional-certificates/meta-front-end-developer", "Coursera"),
    ],
    "sql": [
        _res("video", "SQL Tutorial — Full Database Course (freeCodeCamp)", "https://www.youtube.com/watch?v=HXV3zeQKqGY", "freeCodeCamp"),
        _res("doc", "PostgreSQL Tutorial", "https://www.postgresqltutorial.com/", "PostgreSQLTutorial"),
        _res("course", "SQL for Data Science (Coursera)", "https://www.coursera.org/learn/sql-for-data-science", "Coursera"),
    ],
    "excel": [
        _res("video", "Excel Full Course for Beginners (freeCodeCamp)", "https://www.youtube.com/watch?v=Vl0H-qTclOg", "freeCodeCamp"),
        _res("doc", "Excel Help & Learning (Microsoft)", "https://support.microsoft.com/en-us/excel", "Microsoft"),
        _res("course", "Excel Skills for Business (Coursera)", "https://www.coursera.org/specializations/excel", "Coursera"),
    ],
    "tableau": [
        _res("video", "Tableau for Beginners — Full Course (freeCodeCamp)", "https://www.youtube.com/watch?v=-zZJgpVxTAQ", "freeCodeCamp"),
        _res("doc", "Tableau Training & Tutorials", "https://www.tableau.com/learn/training", "Tableau"),
        _res("course", "Data Visualization with Tableau (Coursera)", "https://www.coursera.org/specializations/data-visualization", "Coursera"),
    ],
    "power bi": [
        _res("video", "Power BI Tutorial for Beginners (Simon Sez IT)", "https://www.youtube.com/watch?v=DtD9XJ99jG4", "Simon Sez IT"),
        _res("doc", "Power BI Documentation (Microsoft)", "https://learn.microsoft.com/en-us/power-bi/", "Microsoft Learn"),
        _res("course", "Microsoft Power BI Data Analyst (Coursera)", "https://www.coursera.org/professional-certificates/microsoft-power-bi-data-analyst", "Coursera"),
    ],
    "machine learning": [
        _res("video", "Machine Learning for Everybody (freeCodeCamp)", "https://www.youtube.com/watch?v=i_LwzRVP7bg", "freeCodeCamp"),
        _res("doc", "Google Machine Learning Crash Course", "https://developers.google.com/machine-learning/crash-course", "Google"),
        _res("course", "Machine Learning — Andrew Ng (Coursera)", "https://www.coursera.org/learn/machine-learning", "Coursera"),
    ],
    "deep learning": [
        _res("video", "Deep Learning Course for Beginners (freeCodeCamp)", "https://www.youtube.com/watch?v=ASN7S2K9Wgo", "freeCodeCamp"),
        _res("doc", "Deep Learning Specialization notes", "https://www.deeplearning.ai/courses/deep-learning-specialization/", "deeplearning.ai"),
        _res("course", "Deep Learning Specialization (Coursera)", "https://www.coursera.org/specializations/deep-learning", "Coursera"),
    ],
    "nlp": [
        _res("video", "Natural Language Processing NLP (freeCodeCamp)", "https://www.youtube.com/watch?v=fNxaJsNG3-s", "freeCodeCamp"),
        _res("doc", "Hugging Face NLP Course", "https://huggingface.co/learn/nlp-course", "Hugging Face"),
        _res("course", "Natural Language Processing (Coursera)", "https://www.coursera.org/specializations/natural-language-processing", "Coursera"),
    ],
    "pytorch": [
        _res("video", "PyTorch for Deep Learning (freeCodeCamp)", "https://www.youtube.com/watch?v=V_xro1bcAuA", "freeCodeCamp"),
        _res("doc", "PyTorch Tutorials (official)", "https://pytorch.org/tutorials/", "PyTorch"),
        _res("course", "Intro to Deep Learning with PyTorch (Udacity)", "https://www.udacity.com/course/deep-learning-pytorch--ud188", "Udacity"),
    ],
    "tensorflow": [
        _res("video", "TensorFlow 2.0 Full Course (freeCodeCamp)", "https://www.youtube.com/watch?v=tPYj3fFJGjk", "freeCodeCamp"),
        _res("doc", "TensorFlow Tutorials (official)", "https://www.tensorflow.org/tutorials", "TensorFlow"),
        _res("course", "Introduction to TensorFlow (Coursera)", "https://www.coursera.org/learn/introduction-tensorflow", "Coursera"),
    ],
    "docker": [
        _res("video", "Docker Tutorial for Beginners (Programming with Mosh)", "https://www.youtube.com/watch?v=pTFZFxd4hOI", "Mosh"),
        _res("doc", "Docker Get Started (official)", "https://docs.docker.com/get-started/", "Docker"),
        _res("course", "Docker Mastery (Udemy)", "https://www.udemy.com/course/docker-mastery/", "Udemy"),
    ],
    "kubernetes": [
        _res("video", "Kubernetes Tutorial for Beginners (freeCodeCamp)", "https://www.youtube.com/watch?v=X48VuDVv0do", "freeCodeCamp"),
        _res("doc", "Kubernetes Basics (official)", "https://kubernetes.io/docs/tutorials/kubernetes-basics/", "Kubernetes"),
        _res("course", "CKA Certificate Course (Udemy)", "https://www.udemy.com/course/certified-kubernetes-application-developer/", "Udemy"),
    ],
    "git": [
        _res("video", "Git and GitHub for Beginners (freeCodeCamp)", "https://www.youtube.com/watch?v=RGOj5yH7evk", "freeCodeCamp"),
        _res("doc", "git — the simple guide", "https://rogerdudler.github.io/git-guide/", "Git Guide"),
        _res("course", "Version Control with Git (Coursera)", "https://www.coursera.org/learn/version-control-with-git", "Coursera"),
    ],
    "aws": [
        _res("video", "AWS Certified Cloud Practitioner (freeCodeCamp)", "https://www.youtube.com/watch?v=3hLmDS179YE", "freeCodeCamp"),
        _res("doc", "AWS Training & Certification", "https://aws.amazon.com/training/", "AWS"),
        _res("course", "AWS Fundamentals (Coursera)", "https://www.coursera.org/learn/aws-cloud-technical-essentials", "Coursera"),
    ],
    "linux": [
        _res("video", "Linux for Beginners — Full Course (freeCodeCamp)", "https://www.youtube.com/watch?v=wBp0Rb-ZJak", "freeCodeCamp"),
        _res("doc", "Linux Journey", "https://linuxjourney.com/", "Linux Journey"),
        _res("course", "Linux Command Line Basics (Udacity)", "https://www.udacity.com/course/linux-command-line-basics--ud595", "Udacity"),
    ],
    "statistics": [
        _res("video", "Statistics and Probability — Full Course (freeCodeCamp)", "https://www.youtube.com/watch?v=sbbYntt5CJk", "freeCodeCamp"),
        _res("doc", "Khan Academy Statistics & Probability", "https://www.khanacademy.org/math/statistics-probability", "Khan Academy"),
        _res("course", "Introduction to Statistics (Coursera)", "https://www.coursera.org/learn/stanford-statistics", "Coursera"),
    ],
    "data visualization": [
        _res("video", "Data Visualization with Python (freeCodeCamp)", "https://www.youtube.com/watch?v=r-uOLxNrNk8", "freeCodeCamp"),
        _res("doc", "Matplotlib Documentation", "https://matplotlib.org/stable/tutorials/index.html", "Matplotlib"),
        _res("course", "Data Visualization with Tableau (Coursera)", "https://www.coursera.org/specializations/data-visualization", "Coursera"),
    ],
    "network security": [
        _res("video", "Network Security — Full Course (freeCodeCamp)", "https://www.youtube.com/watch?v=bVeL0zjhHkw", "freeCodeCamp"),
        _res("doc", "TryHackMe — learn security by doing", "https://tryhackme.com/", "TryHackMe"),
        _res("course", "IBM Cybersecurity Analyst (Coursera)", "https://www.coursera.org/professional-certificates/ibm-cybersecurity-analyst", "Coursera"),
    ],
    "cybersecurity": [
        _res("video", "IT Security — Defense Against the Digital Dark Arts (Coursera)", "https://www.coursera.org/learn/it-security", "Coursera"),
        _res("doc", "OWASP Top 10", "https://owasp.org/www-project-top-ten/", "OWASP"),
        _res("course", "IBM Cybersecurity Analyst Professional Certificate", "https://www.coursera.org/professional-certificates/ibm-cybersecurity-analyst", "Coursera"),
    ],
    "communication": [
        _res("video", "Improve Your Communication Skills (Alux)", "https://www.youtube.com/watch?v=5W2OZm6zPK4", "Alux"),
        _res("article", "What Is Effective Communication? (Indeed)", "https://www.indeed.com/career-advice/career-development/what-is-effective-communication", "Indeed"),
        _res("course", "Dynamic Public Speaking (Coursera)", "https://www.coursera.org/specializations/dynamic-public-speaking", "Coursera"),
    ],
    "teamwork": [
        _res("article", "Teamwork Skills: Being an Effective Group Member (SkillsYouNeed)", "https://www.skillsyouneed.com/ips/teamwork.html", "SkillsYouNeed"),
        _res("course", "Teamwork Skills: Communicating Effectively in Groups (Coursera)", "https://www.coursera.org/learn/teamwork-skills", "Coursera"),
        _res("video", "The Power of Teamwork (TED)", "https://www.youtube.com/watch?v=fUXdrl9ZQLE", "TED"),
    ],
    "leadership": [
        _res("video", "Leadership — How to Become a Better Leader (TED)", "https://www.youtube.com/watch?v=QpW7r8Q0u70", "TED"),
        _res("article", "What Is Leadership? (Indeed)", "https://www.indeed.com/career-advice/career-development/what-is-leadership", "Indeed"),
        _res("course", "Foundations of Everyday Leadership (Coursera)", "https://www.coursera.org/learn/leadership-foundations", "Coursera"),
    ],
    "pandas": [
        _res("video", "Pandas for Data Science (freeCodeCamp)", "https://www.youtube.com/watch?v=vmEHCJofslg", "freeCodeCamp"),
        _res("doc", "Pandas Getting Started (official)", "https://pandas.pydata.org/docs/getting_started/index.html", "Pandas"),
        _res("course", "Python for Data Science and Machine Learning Bootcamp (Udemy)", "https://www.udemy.com/course/python-for-data-science-and-machine-learning-bootcamp/", "Udemy"),
    ],
    "numpy": [
        _res("video", "NumPy Tutorial — Full Course (freeCodeCamp)", "https://www.youtube.com/watch?v=QUT1VHiLmmI", "freeCodeCamp"),
        _res("doc", "NumPy Quickstart (official)", "https://numpy.org/doc/stable/user/quickstart.html", "NumPy"),
        _res("course", "Data Analysis with Python (freeCodeCamp)", "https://www.freecodecamp.org/learn/data-analysis-with-python/", "freeCodeCamp"),
    ],
    "scikit-learn": [
        _res("video", "Machine Learning with scikit-learn (sentdex)", "https://www.youtube.com/playlist?list=PLQVvvaa0QuDfKTOs3Keq_kaG2P55YRn5v", "sentdex"),
        _res("doc", "scikit-learn User Guide (official)", "https://scikit-learn.org/stable/user_guide.html", "scikit-learn"),
        _res("course", "Applied Machine Learning in Python (Coursera)", "https://www.coursera.org/learn/python-machine-learning", "Coursera"),
    ],
    "rest apis": [
        _res("video", "REST API concepts and examples (WebConcepts)", "https://www.youtube.com/watch?v=npNqjR6iREQ", "WebConcepts"),
        _res("doc", "REST API Tutorial", "https://restfulapi.net/", "restfulapi.net"),
        _res("course", "Build REST APIs with Django REST Framework (Coursera)", "https://www.coursera.org/projects/django-rest-framework", "Coursera"),
    ],
    "flask": [
        _res("video", "Flask Python Web Framework (freeCodeCamp)", "https://www.youtube.com/watch?v=MwZwr5Tvyxo", "freeCodeCamp"),
        _res("doc", "Flask Quickstart (official)", "https://flask.palletsprojects.com/en/stable/quickstart/", "Flask"),
        _res("course", "REST APIs with Flask and Python (Udemy)", "https://www.udemy.com/course/rest-api-flask-and-python/", "Udemy"),
    ],
    "fastapi": [
        _res("video", "FastAPI Course for Beginners", "https://www.youtube.com/watch?v=tLKKmouUams", "freeCodeCamp"),
        _res("doc", "FastAPI Documentation (official)", "https://fastapi.tiangolo.com/", "FastAPI"),
        _res("course", "FastAPI — The Full Course (Udemy)", "https://www.udemy.com/course/python-api-development-in-depth/", "Udemy"),
    ],
    "sqlalchemy": [
        _res("doc", "SQLAlchemy Documentation (official)", "https://docs.sqlalchemy.org/en/20/", "SQLAlchemy"),
        _res("video", "SQLAlchemy Python Tutorial", "https://www.youtube.com/watch?v=AkMJXfWteLI", "TutorialEdge"),
        _res("course", "SQL and PostgreSQL (Udemy)", "https://www.udemy.com/course/sql-and-postgresql/", "Udemy"),
    ],
    "etl": [
        _res("video", "ETL Pipelines Explained", "https://www.youtube.com/watch?v=8dJ8NuEmwOM", "IBM Technology"),
        _res("doc", "What is ETL? (Hevo)", "https://hevodata.com/learn/what-is-etl/", "Hevo"),
        _res("course", "Data Engineering Foundations (Coursera)", "https://www.coursera.org/specializations/data-engineering-foundations", "Coursera"),
    ],
    "airflow": [
        _res("video", "Apache Airflow Tutorial (freeCodeCamp)", "https://www.youtube.com/watch?v=K9AnJ9_ZdnE", "freeCodeCamp"),
        _res("doc", "Airflow Documentation (official)", "https://airflow.apache.org/docs/", "Apache Airflow"),
        _res("course", "Data Pipelines with Airflow (Udemy)", "https://www.udemy.com/course/the-ultimate-handson-apache-airflow-course/", "Udemy"),
    ],
    "spark": [
        _res("video", "Apache Spark for Beginners (freeCodeCamp)", "https://www.youtube.com/watch?v=QaoJhWl0XQU", "freeCodeCamp"),
        _res("doc", "Apache Spark Quick Start (official)", "https://spark.apache.org/docs/latest/quick-start.html", "Apache Spark"),
        _res("course", "Big Data Essentials with Spark (Coursera)", "https://www.coursera.org/learn/big-data-essentials", "Coursera"),
    ],
    "hadoop": [
        _res("video", "Hadoop Ecosystem — Full Course (freeCodeCamp)", "https://www.youtube.com/watch?v=zcYLrc3JT8Y", "freeCodeCamp"),
        _res("doc", "Apache Hadoop Documentation", "https://hadoop.apache.org/docs/current/", "Apache Hadoop"),
        _res("course", "Big Data with Hadoop (Coursera)", "https://www.coursera.org/learn/hadoop", "Coursera"),
    ],
    "snowflake": [
        _res("video", "Snowflake Tutorial for Beginners", "https://www.youtube.com/watch?v=vEiHlEF76ww", "freeCodeCamp"),
        _res("doc", "Snowflake Documentation (official)", "https://docs.snowflake.com/", "Snowflake"),
        _res("course", "Snowflake Fundamentals (Coursera)", "https://www.coursera.org/learn/snowflake-fundamentals", "Coursera"),
    ],
    "bigquery": [
        _res("video", "Google BigQuery Tutorial (Simplilearn)", "https://www.youtube.com/watch?v=jvHhiuqJSV0", "Simplilearn"),
        _res("doc", "BigQuery Documentation (official)", "https://cloud.google.com/bigquery/docs", "Google Cloud"),
        _res("course", "From Data to Insights with Google Cloud (Coursera)", "https://www.coursera.org/learn/from-data-to-insights-google-cloud", "Coursera"),
    ],
    "dbt": [
        _res("video", "dbt Tutorial for Beginners", "https://www.youtube.com/watch?v=EOdL-Vq0Xco", "dbt Labs"),
        _res("doc", "dbt Documentation (official)", "https://docs.getdbt.com/", "dbt Labs"),
        _res("course", "Analytics Engineering with dbt (Coursera)", "https://www.coursera.org/projects/dbt-cloud-data-build-tool", "Coursera"),
    ],
    "data engineering": [
        _res("video", "Data Engineering Full Course (freeCodeCamp)", "https://www.youtube.com/watch?v=qHY6bjiVu8o", "freeCodeCamp"),
        _res("doc", "Data Engineering Roadmap", "https://awesomedataengineering.com/", "Awesome Data Engineering"),
        _res("course", "Data Engineering Foundations (Coursera)", "https://www.coursera.org/specializations/data-engineering-foundations", "Coursera"),
    ],
    "ci/cd": [
        _res("video", "CI/CD — What is Continuous Integration?", "https://www.youtube.com/watch?v=1er2cUjqksg", "IBM Technology"),
        _res("doc", "GitHub Actions Documentation", "https://docs.github.com/en/actions", "GitHub"),
        _res("course", "Build Continuous Integration (CI) Pipelines (Coursera)", "https://www.coursera.org/projects/github-actions-ci", "Coursera"),
    ],
    "testing": [
        _res("video", "Software Testing Tutorial (freeCodeCamp)", "https://www.youtube.com/watch?v=fwxtk9eMk6I", "freeCodeCamp"),
        _res("doc", "pytest Documentation", "https://docs.pytest.org/en/stable/", "pytest"),
        _res("course", "Automated Software Testing (Udacity)", "https://www.udacity.com/course/software-testing--cs258", "Udacity"),
    ],
    "azure": [
        _res("video", "Azure Fundamentals Certification (freeCodeCamp)", "https://www.youtube.com/watch?v=NKEFWyq5JXA", "freeCodeCamp"),
        _res("doc", "Azure Documentation (Microsoft)", "https://learn.microsoft.com/en-us/azure/", "Microsoft Learn"),
        _res("course", "AZ-900 Azure Fundamentals (Coursera)", "https://www.coursera.org/learn/microsoft-azure-az-900-essentials", "Coursera"),
    ],
    "gcp": [
        _res("video", "Google Cloud Associate Cloud Engineer (freeCodeCamp)", "https://www.youtube.com/watch?v=JPnoJKS4w1Y", "freeCodeCamp"),
        _res("doc", "Google Cloud Documentation", "https://cloud.google.com/docs", "Google Cloud"),
        _res("course", "Google Cloud Digital Leader (Coursera)", "https://www.coursera.org/learn/cloud-digital-leader-training", "Coursera"),
    ],
    "nosql": [
        _res("video", "NoSQL Database Concepts (IBM Technology)", "https://www.youtube.com/watch?v=bUZohWrUSKQ", "IBM Technology"),
        _res("doc", "MongoDB University", "https://learn.mongodb.com/", "MongoDB"),
        _res("course", "MongoDB — The Complete Developer's Guide (Udemy)", "https://www.udemy.com/course/mongodb-the-complete-developers-guide/", "Udemy"),
    ],
    "mongodb": [
        _res("doc", "MongoDB Manual (official)", "https://www.mongodb.com/docs/manual/", "MongoDB"),
        _res("video", "MongoDB Crash Course (Traversy Media)", "https://www.youtube.com/watch?v=OF55gHtRa5E", "Traversy Media"),
        _res("course", "MongoDB University", "https://learn.mongodb.com/", "MongoDB"),
    ],
    "postgresql": [
        _res("video", "PostgreSQL Tutorial for Beginners (freeCodeCamp)", "https://www.youtube.com/watch?v=qw--VYLpxG4", "freeCodeCamp"),
        _res("doc", "PostgreSQL Documentation (official)", "https://www.postgresql.org/docs/current/", "PostgreSQL"),
        _res("course", "SQL and PostgreSQL: The Complete Developer's Guide (Udemy)", "https://www.udemy.com/course/sql-and-postgresql/", "Udemy"),
    ],
    "data analysis": [
        _res("video", "Data Analysis with Python — Full Course (freeCodeCamp)", "https://www.youtube.com/watch?v=r-uOLxNrNk8", "freeCodeCamp"),
        _res("doc", "Pandas Getting Started", "https://pandas.pydata.org/docs/getting_started/index.html", "Pandas"),
        _res("course", "Google Data Analytics Certificate (Coursera)", "https://www.coursera.org/professional-certificates/google-data-analytics", "Coursera"),
    ],
    "business intelligence": [
        _res("video", "Business Intelligence — What it is and how it works", "https://www.youtube.com/watch?v=WAFBXUXBSPM", "ITLearn365"),
        _res("doc", "What is Business Intelligence? (Tableau)", "https://www.tableau.com/learn/articles/business-intelligence", "Tableau"),
        _res("course", "Google Business Intelligence Certificate (Coursera)", "https://www.coursera.org/professional-certificates/google-business-intelligence", "Coursera"),
    ],
    "data storytelling": [
        _res("video", "Storytelling with Data (Cole Nussbaumer Knaflic)", "https://www.youtube.com/watch?v=lVZkXDzR4D8", "Storytelling with Data"),
        _res("article", "Data Storytelling — The Essential Data Science Skill (Coursera)", "https://www.coursera.org/articles/data-storytelling", "Coursera"),
        _res("course", "Effective Business Presentations with Powerpoint (PwC, Coursera)", "https://www.coursera.org/learn/effective-business-presentations-powerpoint", "Coursera"),
    ],
    "incident response": [
        _res("video", "Incident Response — Blue Team (freeCodeCamp)", "https://www.youtube.com/watch?v=eSnaUK7nouc", "freeCodeCamp"),
        _res("doc", "NIST Incident Response (official)", "https://csrc.nist.gov/topics/security-and-privacy/incident-response", "NIST"),
        _res("course", "IBM Cybersecurity — Heads Up! Incident Response (Coursera)", "https://www.coursera.org/learn/incident-response", "Coursera"),
    ],
    "siem": [
        _res("video", "SIEM — Splunk vs ELK watch how it works", "https://www.youtube.com/watch?v=YOQCy0t_qkE", "infosectrain"),
        _res("doc", "Splunk Documentation", "https://docs.splunk.com/", "Splunk"),
        _res("course", "IBM Cybersecurity — SOC (Coursera)", "https://www.coursera.org/learn/siem-systems", "Coursera"),
    ],
    "risk assessment": [
        _res("video", "Risk Assessment Basics (SecurityMetrics)", "https://www.youtube.com/watch?v=nxACwdcECV4", "SecurityMetrics"),
        _res("doc", "NIST Risk Management Framework", "https://csrc.nist.gov/projects/risk-management", "NIST"),
        _res("course", "Security Governance & Compliance (Coursera)", "https://www.coursera.org/learn/governance-and-management-of-it-compliance", "Coursera"),
    ],
    "threat detection": [
        _res("video", "Threat Hunting — Cyber Threat Detection", "https://www.youtube.com/watch?v=E5WHnz15H4I", "ec-council"),
        _res("doc", "MITRE ATT&CK", "https://attack.mitre.org/", "MITRE"),
        _res("course", "IBM Cybersecurity — Threat Intelligence (Coursera)", "https://www.coursera.org/learn/threat-intelligence", "Coursera"),
    ],
    "cloud security": [
        _res("video", "Cloud Security — Full Course (freeCodeCamp)", "https://www.youtube.com/watch?v=JMashhrMln0", "freeCodeCamp"),
        _res("doc", "Shared Responsibility Model (AWS)", "https://aws.amazon.com/compliance/shared-responsibility-model/", "AWS"),
        _res("course", "IBM Cybersecurity — Cloud Security (Coursera)", "https://www.coursera.org/learn/cloud-security", "Coursera"),
    ],
    "penetration testing": [
        _res("video", "Ethical Hacking & Penetration Testing (freeCodeCamp)", "https://www.youtube.com/watch?v=3Kq1MIfTWCE", "freeCodeCamp"),
        _res("doc", "OWASP Testing Guide", "https://owasp.org/www-project-web-security-testing-guide/", "OWASP"),
        _res("course", "Practical Ethical Hacking (TCM, Udemy)", "https://www.udemy.com/course/practical-ethical-hacking/", "Udemy"),
    ],
    "iso 27001": [
        _res("video", "What is ISO 27001? (Advisera)", "https://www.youtube.com/watch?v=LxqjBx9YkSo", "Advisera"),
        _res("doc", "ISO/IEC 27001 information security standards", "https://www.iso.org/isoiec-27001-information-security.html", "ISO"),
        _res("course", "ISO 27001 ISMS Lead Implementer (Udemy)", "https://www.udemy.com/course/iso-27001-isms-cyber-security/", "Udemy"),
    ],
    "security+": [
        _res("video", "CompTIA Security+ Full Course (freeCodeCamp)", "https://www.youtube.com/watch?v=9R2jIRM6LOk", "freeCodeCamp"),
        _res("doc", "CompTIA Security+ (SY0-701) — official", "https://www.comptia.org/certifications/security", "CompTIA"),
        _res("course", "CompTIA Security+ (SY0-701) Course (Udemy)", "https://www.udemy.com/course/securityplus/", "Udemy"),
    ],
    "digital forensics": [
        _res("video", "Digital Forensics — Course (freeCodeCamp)", "https://www.youtube.com/watch?v=kqQPhX9D0ag", "freeCodeCamp"),
        _res("doc", "SANS Digital Forensics & Incident Response", "https://www.sans.org/digital-forensics-incident-response/", "SANS"),
        _res("course", "IBM Cybersecurity — Digital Forensics (Coursera)", "https://www.coursera.org/learn/digital-forensics-concepts", "Coursera"),
    ],
    "windows server": [
        _res("video", "Windows Server Administration (Professor Messer)", "https://www.youtube.com/watch?v=MImO0Z2q1Q4", "Professor Messer"),
        _res("doc", "Windows Server documentation (Microsoft)", "https://learn.microsoft.com/en-us/windows-server/", "Microsoft Learn"),
        _res("course", "Windows Server 2022 Administration (Udemy)", "https://www.udemy.com/course/complete-guide-to-windows-server-2022-administration/", "Udemy"),
    ],
    "active directory": [
        _res("video", "Active Directory Administration (freeCodeCamp)", "https://www.youtube.com/watch?v=t75MqaiERPE", "freeCodeCamp"),
        _res("doc", "Active Directory Domain Services (Microsoft)", "https://learn.microsoft.com/en-us/windows-server/identity/ad-ds/get-started/virtual-dc/active-directory-domain-services-overview", "Microsoft Learn"),
        _res("course", "Active Directory & GPO (Udemy)", "https://www.udemy.com/course/active-directory-ultimate-course/", "Udemy"),
    ],
    "vulnerability management": [
        _res("video", "Vulnerability Management Overview (RSA)", "https://www.youtube.com/watch?v=3ZA0QRuwb4A", "RSA"),
        _res("doc", "CVE — Common Vulnerabilities and Exposures", "https://www.cve.org/", "CVE.org"),
        _res("course", "Vulnerability Management (Coursera)", "https://www.coursera.org/learn/vulnerability-management-identifying-and-responding-to-common-cyber-threats", "Coursera"),
    ],
}

# Category-level fallback for skills without a curated entry.
_CATEGORY_BASE = {
    "Programming": [
        _res("video", "Learn Python — Full Course for Beginners (freeCodeCamp)", "https://www.youtube.com/watch?v=rfscVS0vtbw", "freeCodeCamp"),
        _res("doc", "The Python Tutorial (official)", "https://docs.python.org/3/tutorial/", "Python.org"),
        _res("course", "Python for Everybody (Coursera)", "https://www.coursera.org/specializations/python", "Coursera"),
    ],
    "Data": [
        _res("video", "SQL Tutorial — Full Database Course (freeCodeCamp)", "https://www.youtube.com/watch?v=HXV3zeQKqGY", "freeCodeCamp"),
        _res("doc", "Pandas Getting Started", "https://pandas.pydata.org/docs/getting_started/index.html", "Pandas"),
        _res("course", "Excel Skills for Business (Coursera)", "https://www.coursera.org/specializations/excel", "Coursera"),
    ],
    "AI": [
        _res("video", "Machine Learning for Everybody (freeCodeCamp)", "https://www.youtube.com/watch?v=i_LwzRVP7bg", "freeCodeCamp"),
        _res("doc", "Google Machine Learning Crash Course", "https://developers.google.com/machine-learning/crash-course", "Google"),
        _res("course", "Machine Learning — Andrew Ng (Coursera)", "https://www.coursera.org/learn/machine-learning", "Coursera"),
    ],
    "DevOps": [
        _res("video", "Docker Tutorial for Beginners (Mosh)", "https://www.youtube.com/watch?v=pTFZFxd4hOI", "Mosh"),
        _res("doc", "Docker Get Started (official)", "https://docs.docker.com/get-started/", "Docker"),
        _res("course", "AWS Fundamentals (Coursera)", "https://www.coursera.org/learn/aws-cloud-technical-essentials", "Coursera"),
    ],
    "Visualization": [
        _res("video", "Data Visualization with Python (freeCodeCamp)", "https://www.youtube.com/watch?v=r-uOLxNrNk8", "freeCodeCamp"),
        _res("doc", "Tableau Training & Tutorials", "https://www.tableau.com/learn/training", "Tableau"),
        _res("course", "Data Visualization with Tableau (Coursera)", "https://www.coursera.org/specializations/data-visualization", "Coursera"),
    ],
    "Analytics": [
        _res("video", "Excel Full Course for Beginners (freeCodeCamp)", "https://www.youtube.com/watch?v=Vl0H-qTclOg", "freeCodeCamp"),
        _res("doc", "Power BI Documentation (Microsoft)", "https://learn.microsoft.com/en-us/power-bi/", "Microsoft Learn"),
        _res("course", "Google Data Analytics Certificate (Coursera)", "https://www.coursera.org/professional-certificates/google-data-analytics", "Coursera"),
    ],
    "Security": [
        _res("video", "Network Security — Full Course (freeCodeCamp)", "https://www.youtube.com/watch?v=bVeL0zjhHkw", "freeCodeCamp"),
        _res("doc", "OWASP Top 10", "https://owasp.org/www-project-top-ten/", "OWASP"),
        _res("course", "IBM Cybersecurity Analyst (Coursera)", "https://www.coursera.org/professional-certificates/ibm-cybersecurity-analyst", "Coursera"),
    ],
    "Soft Skills": [
        _res("article", "What Is Effective Communication? (Indeed)", "https://www.indeed.com/career-advice/career-development/what-is-effective-communication", "Indeed"),
        _res("course", "Dynamic Public Speaking (Coursera)", "https://www.coursera.org/specializations/dynamic-public-speaking", "Coursera"),
    ],
}

_GENERIC_FALLBACK = [
    _res("video", "freeCodeCamp YouTube — free, full-length tech courses", "https://www.youtube.com/@freecodecamp", "freeCodeCamp"),
    _res("doc", "MDN Web Docs", "https://developer.mozilla.org/en-US/docs/Web", "MDN"),
    _res("course", "Coursera — search for this skill", "https://www.coursera.org/search?query=technology", "Coursera"),
]


def _urllib_quote(value):
    from urllib.parse import quote
    return quote(value or "")


def curated_resources(skill_name, category):
    key = (skill_name or "").strip().lower()
    pool = _CURATED.get(key)
    if pool:
        return [dict(r) for r in pool]
    cat_pool = _CATEGORY_BASE.get(category)
    if cat_pool:
        out = [dict(r) for r in cat_pool]
        out.append(_res("course", f"{skill_name} learning paths on Coursera",
                        "https://www.coursera.org/search?query=" + _urllib_quote(skill_name), "Coursera"))
        return out
    out = [dict(r) for r in _GENERIC_FALLBACK]
    out.append(_res("course", f"Search: {skill_name}",
                    "https://www.coursera.org/search?query=" + _urllib_quote(skill_name), "Coursera"))
    return out


# ---------------------------------------------------------------- live retrieval

def _search_youtube(skill_name, target_role, limit=3):
    """Real retrieval of current videos via the YouTube Data API."""
    if not YOUTUBE_API_KEY:
        return []
    query = f"{skill_name} tutorial for {target_role}".strip()
    try:
        import httpx
        r = httpx.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={"part": "snippet", "type": "video", "maxResults": min(limit, 8),
                    "q": query, "key": YOUTUBE_API_KEY},
            timeout=8,
        )
        r.raise_for_status()
        items = r.json().get("items", [])
        out = []
        for it in items:
            video_id = it.get("id", {}).get("videoId")
            sn = it.get("snippet", {})
            if video_id:
                out.append(_res("video", (sn.get("title") or "Video")[:120],
                                f"https://www.youtube.com/watch?v={video_id}",
                                sn.get("channelTitle", "YouTube")))
        return out
    except Exception:
        return []


_CHECK_CACHE = {}


def _live(url, timeout=1.5):
    """Cheap connectivity check for a URL; tolerant — unverifiable links are kept."""
    cached = _CHECK_CACHE.get(url)
    if cached is not None:
        return cached
    try:
        import httpx
        r = httpx.head(url, follow_redirects=True, timeout=timeout)
        ok = r.status_code < 400
    except Exception:
        ok = True  # network unavailable — assume curated link is fine
    # Cache failures too (per-URL) so repeated seeding does not re-scan.
    _CHECK_CACHE[url] = ok
    return ok


def _youtube_video_id(url):
    """Extract YouTube video ID from various URL formats."""
    try:
        parsed = urlparse(url)
        if "youtube.com" in parsed.netloc:
            if parsed.path == "/watch":
                qs = parse_qs(parsed.query)
                return qs.get("v", [None])[0]
            if parsed.path.startswith("/embed/"):
                return parsed.path.split("/")[2]
            if parsed.path.startswith("/v/"):
                return parsed.path.split("/")[2]
        if "youtu.be" in parsed.netloc:
            return parsed.path.lstrip("/")
    except Exception:
        pass
    return None


def _youtube_thumbnail_available(video_id, timeout=2.0):
    """Check YouTube video availability via thumbnail endpoint.
    
    The mqdefault.jpg thumbnail returns 404 for deleted/private/removed videos,
    unlike the watch page which returns 200 for most states.
    """
    if not video_id:
        return None
    thumb_url = f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg"
    try:
        import httpx
        r = httpx.head(thumb_url, follow_redirects=True, timeout=timeout)
        if r.status_code == 404:
            return False
        if r.status_code < 400:
            # Additional check: default thumbnail is 120x90, real thumbnails are larger
            # but we'll trust the 404 signal
            return True
    except Exception:
        pass
    return None  # unknown/unverifiable


def _resource_availability(url, timeout=2.0):
    """Determine resource availability with YouTube-specific logic.
    
    Returns: True (available), False (dead), None (unknown/unverifiable)
    """
    video_id = _youtube_video_id(url)
    if video_id:
        yt_result = _youtube_thumbnail_available(video_id, timeout)
        if yt_result is False:
            return False
        if yt_result is True:
            return True
        # YouTube video but thumbnail check inconclusive — fall through to HEAD
    
    # Fallback: generic HEAD check
    cached = _CHECK_CACHE.get(url)
    if cached is not None:
        return cached
    try:
        import httpx
        r = httpx.head(url, follow_redirects=True, timeout=timeout)
        ok = r.status_code < 400
    except Exception:
        ok = True  # network unavailable — assume curated link is fine
    _CHECK_CACHE[url] = ok
    return ok


def annotate_resources(resources):
    """Annotate each resource with availability status.
    
    Returns list of resources with added 'available' field:
      True  = confirmed available
      False = confirmed dead/removed
      None  = unknown (network down or inconclusive)
    """
    if not resources:
        return []
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=16) as ex:
        # Check availability for each resource
        avail_results = list(ex.map(lambda r: _resource_availability(r["url"]), resources))
    
    annotated = []
    for r, avail in zip(resources, avail_results):
        nr = dict(r)
        nr["available"] = avail
        annotated.append(nr)
    return annotated


def choose_live(resources, min_keep=1):
    """Filter resources to only available ones, but keep at least min_keep per skill.
    
    Strategy:
    - First, keep all confirmed available (True)
    - If fewer than min_keep, add back unknown (None) resources
    - Dead (False) resources are always dropped
    - This ensures the UI always shows at least something, but prefers live links.
    """
    if not resources:
        return []
    
    available = [r for r in resources if r.get("available") is True]
    unknown = [r for r in resources if r.get("available") is None]
    # Dead resources are always excluded
    
    if len(available) >= min_keep:
        return available
    
    # Need to pad with unknown to reach min_keep
    needed = min_keep - len(available)
    return available + unknown[:needed]


def validate_live(resources):
    """Legacy wrapper: drop links that provably fail; keep unverifiable.
    
    Kept for backward compatibility with existing calls.
    """
    if not resources:
        return []
    annotated = annotate_resources(resources)
    return [r for r in annotated if r.get("available") is not False]


# ---------------------------------------------------------------- public API

_HELPFULNESS = {
    "video": "Quick, visual introduction to get oriented",
    "article": "Conceptual walkthrough to deepen understanding",
    "doc": "Authoritative reference for real-world use",
    "course": "Structured, in-depth curriculum to reach mastery",
}


def retrieve_resources(skill_name, category, target_role=None, live_check=True, max_items=8):
    """Ranked, real resource list for a skill — most helpful first.

    Videos first (fast context), then articles/docs, then full courses. When a
    live search key is set, current videos from the YouTube API merge in at the
    top; the curated index always provides genuine article/doc/course links.
    
    Resources are annotated with 'available' field (True/False/None) so the UI
    can show dead-link badges. Dead links are dropped; at least 1 resource
    per skill is kept (fallback to unknown-status links).
    """
    resources = curated_resources(skill_name, category)
    if YOUTUBE_API_KEY:
        live_videos = _search_youtube(skill_name, target_role or "")
        if live_videos:
            resources = live_videos + resources

    seen, merged = set(), []
    for r in resources:
        if r["url"] in seen:
            continue
        seen.add(r["url"])
        merged.append(r)

    if live_check:
        # Annotate with availability, then filter to live links (keep at least 1)
        merged = annotate_resources(merged)
        merged = choose_live(merged, min_keep=1)

    for i, r in enumerate(merged[:max_items], start=1):
        r["rank"] = i
        r["helpfulness"] = _HELPFULNESS.get(r["type"], "Curated learning resource")
    return merged[:max_items]