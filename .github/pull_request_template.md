## Description

<!-- Provide a brief summary of the changes in this PR -->

## Type of Change

<!-- Mark the appropriate option(s) with an 'x' -->

- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update
- [ ] Refactoring (no functional changes)
- [ ] Performance improvement
- [ ] Infrastructure/DevOps changes

## Areas Affected

<!-- Mark all that apply with an 'x' -->

- [ ] Services (backend APIs)
- [ ] Jobs (data processing/ETL)
- [ ] Frontend (UI/UX)
- [ ] Libraries (shared code)
- [ ] Infrastructure (Terraform, K8s, Docker)
- [ ] Tests
- [ ] Documentation

## Pre-Submission Checklist

### Code Quality

- [ ] Code follows the project's style guidelines
- [ ] Self-review of code has been performed
- [ ] Code is well-commented, particularly in hard-to-understand areas
- [ ] No unnecessary console.log or print statements left in code
- [ ] No commented-out code blocks (unless with explanation)

### Python-Specific Checks (if applicable)

- [ ] **ruff** linting checks pass (`ruff check .`)
- [ ] **ruff** formatting checks pass (`ruff format --check .`)
- [ ] **pylint** checks pass with acceptable score (> 9.0)
- [ ] **pytest** - All existing tests pass
- [ ] **pytest** - New tests added for new functionality
- [ ] **pytest** - Test coverage is adequate for changes (> 80%)
- [ ] Type hints added for all methods
- [ ] Virtual environment dependencies updated (pyproject.toml)

### Frontend-Specific Checks (if applicable)

- [ ] ESLint checks pass (`npm run lint`)
- [ ] Build completes successfully (`npm run build`)
- [ ] All tests pass (`npm run test`)
- [ ] New tests added for new components/features
- [ ] UI renders correctly across different screen sizes
- [ ] No console errors or warnings in browser
- [ ] Dependencies updated in package.json if needed

### Documentation

- [ ] README updated (if applicable)
- [ ] API documentation updated (if applicable)
- [ ] Inline code documentation added/updated
- [ ] Database schema changes documented (if applicable)
- [ ] Environment variables documented (if applicable)

### Repository-Specific

- [ ] Changes follow the monorepo structure and conventions
- [ ] Shared libraries updated appropriately (if applicable)
- [ ] Docker images build successfully (if applicable)
- [ ] Kubernetes manifests updated (if applicable)
- [ ] Terraform plans reviewed (if applicable)

## Testing Instructions

<!-- Describe how reviewers can test these changes -->

1. 
2. 
3. 

## Screenshots (if applicable)

<!-- Add screenshots to demonstrate UI changes -->

## Related Issues

<!-- Link any related issues using #issue_number -->

Closes #

## Additional Notes

<!-- Any additional information that reviewers should know -->
