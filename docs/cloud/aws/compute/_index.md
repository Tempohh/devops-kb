---
title: "AWS Compute"
slug: compute-aws
category: cloud
tags: [aws, compute, ec2, lambda, ecs, eks, fargate, serverless, containers]
search_keywords: [AWS compute, EC2, Lambda, ECS, EKS, Fargate, App Runner, Batch, Lightsail, serverless, containers, virtual machines]
parent: cloud/aws/_index
related: [cloud/aws/networking/vpc, cloud/aws/storage/s3, cloud/aws/storage/ebs-efs-fsx]
official_docs: https://aws.amazon.com/products/compute/
status: complete
difficulty: beginner
last_updated: 2026-02-25
---

# AWS Compute

AWS offre un ampio spettro di opzioni compute — da VM tradizionali (EC2) a serverless (Lambda) a container orchestration (ECS/EKS).

## Sezioni

<div class="grid cards" markdown>

- :material-server: **[EC2 — Elastic Compute Cloud](ec2.md)**

    Instance types, pricing, AMI, User Data, storage, placement groups

- :material-auto-fix: **[EC2 Auto Scaling & Load Balancing](ec2-autoscaling.md)**

    ASG, ALB/NLB/GWLB, scaling policies, Target Tracking, Step Scaling

- :material-lambda: **[Lambda — Serverless](lambda.md)**

    Trigger, concurrency, layers, Lambda@Edge, cold start, VPC, destinations

- :material-docker: **[ECS, EKS & Containers](containers-ecs-eks.md)**

    ECS (EC2 + Fargate), EKS managed, ECR, App Runner, Copilot

</div>

---

## Panoramica Servizi Compute

| Servizio | Tipo | Quando usare |
|---------|------|-------------|
| **EC2** | VM managed | Controllo completo OS, lift-and-shift, licenze BYOL |
| **Lambda** | Serverless | Evento-driven, breve durata (<15min), pay-per-use |
| **ECS + Fargate** | Container serverless | Container senza gestire EC2 |
| **ECS + EC2** | Container su EC2 | Controllo infrastruttura, spot instances |
| **EKS** | Kubernetes managed | Kubernetes workloads, portabilità |
| **App Runner** | Container PaaS | Applicazioni web containerizzate, zero infra |
| **Elastic Beanstalk** | PaaS | Deploy applicazioni senza gestire infra (legacy) |
| **Batch** | Batch computing | Job batch, HPC, ML training su scale |
| **Lightsail** | VPS semplificato | Piccole app, WordPress, costi fissi prevedibili |
| **Outposts** | On-premises | AWS in datacenter proprio |
