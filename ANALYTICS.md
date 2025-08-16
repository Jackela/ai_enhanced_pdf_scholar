# Data & Analytics Specification

This document outlines the data tracking plan for AI Enhanced PDF Scholar. Its purpose is to ensure we capture the necessary data to measure product performance, understand user behavior, and make data-driven decisions.

---

## 1. Key Performance Indicators (KPIs)

These are the high-level metrics we use to measure the success of the product.

| KPI | Description | How to Measure | Rationale |
| :--- | :--- | :--- | :--- |
| **User Engagement** | How active and deeply users are using the platform. | Daily Active Users (DAU) / Monthly Active Users (MAU) ratio; Number of RAG queries per session. | A high ratio indicates the product is valuable and sticky. |
| **User Retention** | The percentage of users who return to the product over time. | Week 1 and Week 4 cohort retention rate. | Measures the long-term value and stickiness of the product. |
| **Feature Adoption** | The percentage of active users who use key features. | % of DAU who use RAG Query; % of DAU who use Citation Extraction. | Helps us understand which features provide the most value. |
| **Conversion Rate** | The percentage of new visitors who sign up for an account. | (Number of new signups / Number of unique visitors) * 100. | Measures the effectiveness of our landing page and value proposition. |

---

## 2. Event Tracking Plan

To calculate our KPIs and conduct behavioral analysis, we will track the following events.

| Event Name | Trigger | Properties | Rationale |
| :--- | :--- | :--- | :--- |
| `user_signup` | A user successfully creates a new account. | `userId`, `signupMethod` (e.g., 'email', 'google') | To measure the user acquisition funnel and understand which signup methods are most popular. |
| `user_login` | An existing user successfully logs in. | `userId` | To track user activity and calculate DAU/MAU. |
| `document_upload_started` | A user initiates a file upload. | `userId`, `fileSize`, `fileType` | To understand upload patterns and potential friction points. |
| `document_upload_success` | A document is successfully uploaded and processed. | `userId`, `documentId`, `processingTimeMs` | To track the success rate and performance of our core upload feature. |
| `document_upload_failed` | A document upload fails. | `userId`, `fileName`, `failureReason` | To identify and diagnose issues in the upload pipeline. |
| `rag_query_executed` | A user asks a question about a document. | `userId`, `documentId`, `queryLength`, `responseTimeMs` | This is our core value metric. It helps us measure engagement and performance. |
| `citation_export_clicked` | A user clicks the button to export citations. | `userId`, `documentId`, `exportFormat` | To measure the adoption and usage of the citation analysis feature. |
| `subscription_started` | A user successfully subscribes to a paid plan. | `userId`, `planType` (e.g., 'monthly', 'annual') | To track revenue and business growth (future-looking). |
| `invite_team_member` | A user invites another person to collaborate. | `userId`, `invitedUserEmail` | To measure the adoption of collaboration features (future-looking). |
