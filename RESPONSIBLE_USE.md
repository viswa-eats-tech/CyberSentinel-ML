# Responsible Use

This project is intended for educational, research and defensive security learning purposes.

It demonstrates an end-to-end machine learning workflow for binary intrusion detection on the UNSW-NB15 dataset. It does not provide a complete production intrusion detection system.

## Appropriate Use

Appropriate uses include:

- learning ML engineering workflows for cybersecurity datasets
- studying binary classification metrics for intrusion detection
- experimenting with preprocessing, threshold selection and model comparison
- demonstrating FastAPI model serving and basic monitoring
- building a portfolio project with transparent limitations

## Inappropriate Use

Do not use this project to:

- scan, attack or disrupt systems without authorization
- make production security decisions without independent validation
- claim protection against real-world attacks
- process private network traffic without permission
- redistribute datasets or model artifacts without the required rights
- hide, automate or enable harmful activity

## Operational Boundaries

The model predicts on tabular flow records with the same schema expected from UNSW-NB15. It does not inspect packets, perform live monitoring or validate behavior on modern production traffic.

Predictions should be treated as model outputs, not as authoritative security decisions.

## Dataset And Citation Responsibility

The UNSW-NB15 dataset is not included in this repository. Users are responsible for obtaining it from an authorized source and following the dataset authors' citation requirements.

The README lists the dataset page and required UNSW-NB15 citations.

## Transparency

When presenting this project, include the documented limitations:

- dataset-specific evaluation
- no live traffic capture
- no authentication or authorization
- no model drift monitoring
- no continuous retraining
- no production incident response workflow

Clear boundaries make the project more credible and prevent overstating what the system does.
