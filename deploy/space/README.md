---
title: SafeOrder
colorFrom: blue
colorTo: yellow
sdk: docker
app_port: 7860
pinned: false
short_description: Sandbox prototype with synthetic data and simulated money
---

# SafeOrder (sandbox prototype)

A hackathon prototype for safer Facebook-commerce payments in Bangladesh: a seller **Trust Check**
before paying, a **Safe Order** that holds the money until delivery, and an **evidence analyzer**
that helps a human analyst decide disputes.

> **Everything here is a sandbox.** The data is synthetic, the money is simulated, nothing is
> validated on real data, and this is not a product of upay or any other company.

- Buyer screens: `/` (Trust Check and Safe Order), `/order/<id>`
- Analyst console: `/analyst`
- Evaluation numbers: `/metrics`
- Demo controls: `/demo` (may need a demo code)

The free Space goes to sleep after a period without visitors; the first request afterwards takes
a minute or two. Open it once before a demonstration.
