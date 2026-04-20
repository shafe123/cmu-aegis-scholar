---
name: Integration Test
about: Request and plan an integration test between two components
title: '[Integration Test] <Component A> ↔ <Component B>'
labels: test, integration
assignees: ''
---

## Objective
Describe the integration that needs to be validated and why it matters.

**User/System Statement:**
As a [role/system], I want to verify that [Component A] integrates correctly with [Component B] so that [expected outcome/business value].

## Components Under Test
- **Component A:** [Name, service, module, or UI element]
- **Component B:** [Name, service, module, or data store]
- **Interface/Touchpoint:** [API, event, function call, queue, database contract, etc.]

## Test Scenario
Describe the end-to-end behavior that should be tested.

- **Trigger/Input:** [What starts the flow?]
- **Expected Interaction:** [How should the components communicate?]
- **Expected Result:** [What should happen if the integration works?]

## Preconditions / Test Data
List any setup required before the test can run.

- Required environment/config:
- Seed data or fixtures:
- Authentication/permissions needed:
- External dependencies or mocks allowed:

## Acceptance Criteria
- [ ] A reproducible integration test is added
- [ ] The test validates communication between both components
- [ ] Success and failure paths are covered where applicable
- [ ] Required test data/setup is documented
- [ ] The test runs in CI or is clearly marked with execution steps

## Definition of Done
- [ ] Test added in the appropriate test suite
- [ ] Relevant documentation updated if needed
- [ ] Existing tests continue to pass
- [ ] Reviewer can follow the reproduction/verification steps

## Suggested Implementation Notes
Add any technical notes, file locations, related services, or constraints that may help implementation.

## Related Issues / PRs
Link related work here.
