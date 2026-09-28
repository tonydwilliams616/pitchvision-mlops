# Bootstrap

One-time foundation for the project, applied manually by an admin (not by CI).

Creates:
- S3 bucket for Terraform state (versioned, encrypted, TLS-only, public access blocked, `prevent_destroy`)
- GitHub Actions OIDC provider
- `pitchvision-github-plan` role - read-only, assumable from pull requests
- `pitchvision-github-apply` role - assumable only from the `production` GitHub environment

## First-time setup

```bash
cd terraform/bootstrap
terraform init
terraform plan
terraform apply
```

State starts local, then is migrated into the bucket it created:

1. Add a `backend.tf` using the `backend_config_example` output (key `bootstrap/terraform.tfstate`)
2. `terraform init -migrate-state`
3. Delete the local `terraform.tfstate*` files once the migration succeeds

## Notes
- If the account already has a GitHub OIDC provider, set `create_github_oidc_provider = false`.
- The bucket has `prevent_destroy`, so it can't be destroyed by accident. This stack is never torn down.
