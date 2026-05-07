
type CubeSchema = {
  name: string;
  title: string;
  description?: string;
  measures: Array<{ name: string; title: string; type: string; description?: string }>;
  dimensions: Array<{ name: string; title: string; type: string; description?: string }>;
  segments: Array<{ name: string; title: string; description?: string }>;
};

type NLQueryResult = {
  query: Record<string, any>;
  explanation: string;
};

function buildSchemaContext(cubes: any[]): CubeSchema[] {
  return cubes.map((cube) => ({
    name: cube.name,
    title: cube.title,
    description: cube.description,
    measures: (cube.measures || [])
      .filter((m: any) => m.public !== false)
      .map((m: any) => ({
        name: m.name,
        title: m.title,
        type: m.aggType || m.type,
        description: m.description,
      })),
    dimensions: (cube.dimensions || [])
      .filter((d: any) => d.public !== false)
      .map((d: any) => ({
        name: d.name,
        title: d.title,
        type: d.type,
        description: d.description,
      })),
    segments: (cube.segments || [])
      .filter((s: any) => s.public !== false)
      .map((s: any) => ({
        name: s.name,
        title: s.title,
        description: s.description,
      })),
  }));
}

function buildSystemPrompt(schema: CubeSchema[]): string {
  return `You are a Cube.js query builder assistant.
Use the official Cube query format. Given the data model below, generate the smallest valid Cube.js JSON query that answers the user's question.

## Data Model
${JSON.stringify(schema, null, 2)}

## Query Members
All query properties are optional unless the question requires them.

* \`measures\`: Use for aggregated metrics, counts, sums, averages, ratios, rankings, and other KPI-style questions.
* \`dimensions\`: Use for grouping, listing, segmentation, unique values, and attribute lookups. A query may contain only dimensions.
* \`segments\`: Use only when a matching segment exists in the data model and the question matches its meaning.
* \`filters\`: Use for constraints on dimensions or measures. Prefer simple filters; use \`and\` / \`or\` only when the question requires boolean logic.
* \`timeDimensions\`: Use for time filtering and time grouping. Include \`granularity\` only when the user wants a time breakdown. If the user only wants a date restriction, omit \`granularity\`.
* \`order\`: Optional. Omit it unless the user asks for sorting or the result would be ambiguous without it. If omitted, Cube default ordering applies.
* \`limit\`: Optional. Use for top-N, ranking, or when the user is asking for a list that could be large.
* \`offset\`: Optional.
* \`total\`: Optional.
* \`timezone\`: Optional, only when relevant to the time question.

## Query Format
{
  "measures": ["CubeName.measureName"],
  "dimensions": ["CubeName.dimensionName"],
  "filters": [{"member": "CubeName.dimensionName", "operator": "equals", "values": ["value"]}],
  "timeDimensions": [{"dimension": "CubeName.timeDimension", "granularity": "day", "dateRange": "last 30 days"}],
  "limit": 100,
  "order": {"CubeName.measureName": "desc"}
}

## Rules
- Only use members (measures, dimensions, segments) that exist in the data model above
- Use the exact member names as shown (e.g. "Orders.count", not "count")
- Do not invent fields, dimensions, measures, segments, operators, or time granularities
- Do not force a measure when the question can be answered with dimensions and/or filters alone
- Do not force a dimension when the question is purely metric-focused and dimensions are unnecessary
- Prefer the minimal query shape that answers the question accurately
- Always include an "_explanation" field at the top level describing what the query does in one sentence
- "filters" operator must be one of: equals, notEquals, contains, notContains, startsWith, notStartsWith, endsWith, notEndsWith, gt, gte, lt, lte, set, notSet, inDateRange, notInDateRange, beforeDate, beforeOrOnDate, afterDate, afterOrOnDate, measureFilter
- Operator availability depends on member type; use only operators that make sense for the selected measure, dimension, or time dimension
- Return ONLY a valid JSON object, no markdown code blocks, no extra text`;
}

export async function generateNLQuery(
  cubes: any[],
  naturalLanguage: string
): Promise<NLQueryResult> {
  const apiKey = process.env.OPENAI_API_KEY;
  const model = process.env.CUBEJS_AI_MODEL || 'gpt-4o';

  if (!apiKey) {
    throw new Error(
      'OPENAI_API_KEY is not set. Please configure it to use AI query generation.'
    );
  }

  const schema = buildSchemaContext(cubes);
  const systemPrompt = buildSystemPrompt(schema);

  const response = await fetch('https://api.openai.com/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${apiKey}`,
    },
    body: JSON.stringify({
      model,
      max_tokens: 2048,
      messages: [
        { role: 'system', content: systemPrompt },
        { role: 'user', content: naturalLanguage },
      ],
    }),
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(`LLM API error (${response.status}): ${err}`);
  }

  const data = (await response.json()) as any;
  const rawText: string = data?.choices?.[0]?.message?.content ?? '';

  // Parse JSON from LLM response
  let parsed: Record<string, any>;
  try {
    parsed = JSON.parse(rawText.trim());
  } catch {
    // Try to extract JSON block if model added markdown fences
    const match = rawText.match(/```(?:json)?\s*([\s\S]*?)```/);
    if (match) {
      parsed = JSON.parse(match[1].trim());
    } else {
      throw new Error('LLM returned non-JSON response');
    }
  }

  const explanation: string = parsed._explanation ?? '';
  delete parsed._explanation;

  return { query: parsed, explanation };
}
