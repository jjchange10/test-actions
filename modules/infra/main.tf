resource "null_resource" "infra" {
  triggers = {
    value = "test-dry-run-both"
  }
}
