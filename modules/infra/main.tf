resource "null_resource" "infra" {
  triggers = {
    value = "test-cumulative-dry-run"
  }
}
