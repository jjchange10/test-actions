resource "null_resource" "apps" {
  triggers = {
    value = "test-dry-run-both"
  }
}
