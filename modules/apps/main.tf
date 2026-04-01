resource "null_resource" "apps" {
  triggers = {
    value = "test-cumulative-dry-run"
  }
}
