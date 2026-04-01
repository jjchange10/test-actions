resource "null_resource" "apps" {
  triggers = {
    value = "test-pr-only-release-notes"
  }
}
