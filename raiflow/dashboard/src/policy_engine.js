/**
 * RaiFlow | Policy-to-Code Engine for Gemma 4
 * This engine translates natural language policies into executable checks 
 * and leverages Gemma 4's native function calling for enforcement.
 */

export class RaiFlowEngine {
    constructor(model = 'gemma4:9b') {
        this.model = model;
        this.endpoint = 'http://localhost:11434/api/chat';
    }

    /**
     * Define a policy and "compile" it for Gemma 4
     */
    async validate(prompt, context, policy) {
        const systemPrompt = `
      You are the RaiFlow Compliance Engine powered by Gemma 4.
      Your task is to analyze the following User Prompt and RAG context against the policy: "${policy.desc}".
      
      If the policy is violated, use the 'report_violation' function.
      If it is safe, respond with 'ALLOW'.
    `;

        // Gemma 4 Function Definition
        const tools = [
            {
                type: 'function',
                function: {
                    name: 'report_violation',
                    description: 'Reports a policy violation in the input or output.',
                    parameters: {
                        type: 'object',
                        properties: {
                            policy_id: { type: 'string' },
                            reason: { type: 'string', description: 'Detailed reasoning for violation' },
                            risk_score: { type: 'number', minimum: 0, maximum: 1 },
                            suggested_remediation: { type: 'string' }
                        },
                        required: ['policy_id', 'reason', 'risk_score']
                    }
                }
            }
        ];

        try {
            const response = await fetch(this.endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    model: this.model,
                    messages: [
                        { role: 'system', content: systemPrompt },
                        { role: 'user', content: `Prompt: ${prompt}\n\nContext: ${context}` }
                    ],
                    tools: tools,
                    stream: false
                })
            });

            if (!response.ok) throw new Error(`Ollama Error: ${response.statusText}`);

            const data = await response.json();
            return data.message;

        } catch (err) {
            console.error('RaiFlow Engine Error:', err);
            // Fallback to local regex-based heuristic if Ollama is unavailable
            return this.heuristicCheck(prompt, policy);
        }
    }

    heuristicCheck(input, policy) {
        // Simple mock heuristic for the demo if the model is offline
        if (policy.title === 'PII Shield' && (input.includes('@') || input.match(/\d{3}-\d{2}-\d{4}/))) {
            return {
                tool_calls: [{
                    function: {
                        name: 'report_violation',
                        arguments: JSON.stringify({
                            policy_id: policy.id,
                            reason: 'Potential Email or SSN detected in heuristic scan.',
                            risk_score: 0.95
                        })
                    }
                }]
            };
        }
        return { content: 'ALLOW' };
    }
}
