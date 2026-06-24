export const meta = {
    name: 'dag-verify-chain',
    description: 'DAG pilot: 铁壁(audit)→破阵(attack)→门神(gate) chain for pre-deploy verification',
    phases: [
        { title: 'Audit', detail: '铁壁 security audit on target' },
        { title: 'Attack', detail: '破阵 red team on audit findings' },
        { title: 'Gate', detail: '门神 quality gate on combined results' },
    ],
}

// ============================================================
// DAG 验证链 Pilot — 铁壁 → 破阵 → 门神
// ============================================================
// Mimics the "验证" lifecycle phase from skill_dag.json.
// Usage: pass {target: "campus_go/internal/handlers/activities.go"}
// Each skill's output feeds into the next skill as context.
// ============================================================

const target = args.target || 'campus_go/'
const context = args.context || 'pre-deploy verification of latest changes'

phase('Audit')
log(`Starting DAG verify chain on: ${target}`)

// Step 1: 铁壁 — full security audit
const auditResult = await agent(
    `Security audit target: ${target}

Context: ${context}

Perform a comprehensive security audit:
1. Check for hardcoded secrets/keys
2. Check for missing input validation
3. Check for missing auth/authz checks
4. Check for SQL injection vectors
5. Check for sensitive data exposure

Output a structured findings report with:
- Finding ID, severity (CRITICAL/HIGH/MEDIUM/LOW), CWE, file:line, description

Focus on HIGH and CRITICAL findings only. Skip LOW noise.`,
    { label: '铁壁-audit', phase: 'Audit', agentType: 'security-auditor' }
)

log(`铁壁 audit complete. Findings received.`)

// Step 2: 破阵 — attack the findings from 铁壁
phase('Attack')
const attackResult = await agent(
    `Based on the security audit findings below, attempt to exploit the discovered vulnerabilities:

=== AUDIT FINDINGS ===
${auditResult}

Target: ${target}
Production server: 139.196.50.134

For each HIGH or CRITICAL finding, attempt to:
1. Construct a working exploit
2. Prove the vulnerability is exploitable (not theoretical)
3. Chain vulnerabilities if possible (two LOWs = one HIGH)

Iron Law: NO VULNERABILITY CLAIM WITHOUT REPRODUCIBLE EXPLOIT PATH.`,
    { label: '破阵-attack', phase: 'Attack', agentType: 'red-team-wolf' }
)

log(`破阵 attack complete.`)

// Step 3: 门神 — quality gate on combined results
phase('Gate')
const gateResult = await agent(
    `Assess whether the target is ready for deployment based on:

=== AUDIT FINDINGS ===
${auditResult}

=== ATTACK RESULTS ===
${attackResult}

Target: ${target}

Gate criteria:
- CRITICAL findings with working exploit → BLOCK
- HIGH findings without exploit → WARN, proceed with caution
- All findings addressed or mitigated → PASS

Output gate decision: PASS / WARN / BLOCK with justification.`,
    { label: '门神-gate', phase: 'Gate', agentType: 'api-tester' }
)

log(`DAG verify chain complete. Gate decision: ${gateResult}`)

return {
    audit: auditResult,
    attack: attackResult,
    gate: gateResult,
}
