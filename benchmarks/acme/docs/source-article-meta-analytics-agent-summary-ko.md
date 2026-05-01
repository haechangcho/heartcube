# Inside Meta’s Home Grown AI Analytics Agent

- Source: https://medium.com/@AnalyticsAtMeta/inside-metas-home-grown-ai-analytics-agent-4ea6779acfb3
- Author: Analytics at Meta
- Published: 2026-03-30
- Retrieved: 2026-04-26
- Note: This file is a Korean summary and structured outline of the article. The original article text is not reproduced verbatim here.

## Summary

This article explains how Meta built an internal AI analytics agent that can autonomously perform routine data analysis work. The core idea is that a large share of analyst work is repetitive and stays within a bounded set of familiar tables, which makes the problem much more tractable for an agent than open-ended analytics would normally suggest.

The system became useful because it was not just given SQL execution capability. It was also given personal context from each analyst's query history, broader business context from searchable internal documentation, and an iterative loop that can run analysis, inspect results, and decide what to do next.

Meta describes a layered knowledge system built around Cookbooks, Recipes, and Ingredients. Those layers let teams encode domain knowledge, validation rules, documentation, and standard workflows so the agent behaves more like a domain expert than a generic chat interface with database access.

## Section Notes

### From Hack to Company-Wide Tool

A data scientist first prototyped the agent on an internal development server using Meta's coding agent. The early version could run SQL against the data warehouse and use limited colleague query history for context. An early real-world test asked the agent to investigate a drop in a health metric, and it reportedly identified the relevant tables, ran multiple diagnostics, and traced the issue to a recent code change.

That early success changed how people perceived the tool. Instead of using AI only for shallow assistance such as syntax fixes or document search, teams saw value in an autonomous agent that could investigate issues end-to-end. The prototype moved into production, went through alpha and beta feedback loops, and then expanded rapidly. Within about six months, the article says weekly usage reached 77% of Meta data scientists and data engineers, plus a much larger set of users in non-data roles.

### The 80/20 Hypothesis: Making the Problem Tractable

The article argues that analytics work is far more repetitive than many people assume. A key internal observation was that 88% of data-scientist queries on a given day only depended on tables the same person had already queried during the prior 90 days.

That constraint matters because the global data warehouse is huge, but each analyst usually operates inside a much smaller working set. The agent becomes practical when it starts from that smaller personal domain instead of searching the full warehouse from scratch each time.

### How Analytics Agent Works

Meta frames the agent as needing the same tools and context a human analyst would need. The article highlights three major pieces:

1. Discover data and gather context.
2. Use an iterative reasoning loop that can write queries, run them, inspect outputs, and choose next steps.
3. Return answers transparently so users can inspect the evidence.

### Discover Data & Gather Context

The system builds a form of shared memory for each analyst. Offline language-model pipelines process the person's historical queries and generate descriptions of commonly used tables, usage patterns, example queries, and related analytical habits. Those artifacts are stored so the agent can retrieve them when needed.

The article also says the agent can search broader knowledge sources such as documentation, warehouse metadata, source code for data pipelines, and semantic models. This combines personal context with organizational context.

An interesting detail is that the product can point the agent at another person's query history, which effectively lets a user borrow that colleague's working context for a task.

### Iterative Reasoning Loop

The article presents analytics as a domain where an agent can fully close the execution loop. Rather than just suggesting SQL, the agent can run a query, inspect the actual result, generate a new hypothesis, and continue until it has a plausible explanation.

The signup-drop example is used to illustrate that process: the agent could check the primary metric, see that the surface numbers did not explain the issue, inspect logging or schema changes, and trace the problem to a deployment-related cause.

### Answer

Meta emphasizes transparency as a core requirement because analytics is only useful when users can verify the answer. The article says each surfaced data point is accompanied by the SQL that produced it, and the user can inspect the reasoning path rather than trusting a hidden conclusion.

### Advanced Features

Once the base system worked, teams wanted a way to inject more team-specific context. That led to a layered knowledge model inspired by cooking terminology:

- Cookbooks
- Recipes
- Ingredients

These layers are designed to capture team knowledge, standard procedures, and domain-specific definitions so the agent improves beyond individual query history.

### Cookbooks

A Cookbook is described as the top-level package for a team or business domain. It can bundle prompts, context, recipes, ingredients, and business guidance so that a conversation starts with the relevant domain framing already attached.

### Recipes

Recipes define how the agent should perform analysis. In practice, that can include:

- which experts' historical query patterns to learn from
- persistent instructions and business rules
- validation checks written in natural language
- limits on which tools or data sources the agent may use

The article's core distinction is that Recipes define the procedure, not the meaning of the data.

### Ingredients

Ingredients hold the domain knowledge itself. The article gives examples such as semantic models, documentation pages, free-form notes, naming conventions, known data quality issues, required filters, and memory captured from user corrections.

This is the layer that tells the agent what the tables, columns, and metrics actually mean in practice.

### How the Layers Work Together

The hierarchy is:

- Cookbooks package the right setup for a domain.
- Recipes describe how to analyze.
- Ingredients describe what the domain concepts mean.

The claimed benefit is that team knowledge can be encoded once and reused broadly, reducing reliance on each analyst individually remembering every table choice, join rule, filter, or validation habit.

## Key Lessons Highlighted in the Article

### Start With a Falsifiable Bet

Meta says the project began from a measurable hypothesis rather than a vague claim that AI could help with analytics. The repeat-pattern statistic around historical table reuse made the problem concrete and testable.

### Personal Context Is a Killer Feature

The article treats personalized context as the main reason the system works. Without narrowing the search space, an agent would drown in irrelevant tables and weakly grounded guesses. Personal query history gives the model a bounded domain from the first interaction.

### Show Your Work

The article strongly argues that in analytics, unverifiable answers are not enough. Surfacing the underlying SQL and reasoning steps is positioned as a product requirement rather than a nice extra.

### Your Community Is Your Product Team

The product appears to have grown through heavy internal user involvement. The article cites large volumes of feedback posts, internal talks, and community-created recipes. It frames early users as co-builders whose requests directly shaped the product roadmap.

### Ship Early, Learn Fast

The final lesson is about speed. The article describes the product moving from a rough weekend prototype to a broadly used internal tool in roughly six months, with learning driven by frequent real-world use rather than long pre-launch polishing cycles.

## Key Numbers Mentioned

- 77% weekly adoption among Meta data scientists and data engineers after about six months
- roughly 5x as many users from non-data roles
- 88% of daily data-scientist queries relying only on tables used in the prior 90 days
- 70,000+ employees served by the broader warehouse environment described in the article
- 750+ feedback posts, 130+ wins and best-practice posts, and 40+ community talks in H2 2025
- 4,500+ community-created recipes reportedly used 150,000 times by open beta

## Practical Takeaway

The article's broader claim is that AI analytics agents become useful when the problem is narrowed to a tractable domain and when organizational knowledge is turned into reusable system context. Raw model capability is not presented as the main differentiator. The differentiators are scoped search, personal memory, transparent execution, and structured domain knowledge.
