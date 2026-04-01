resource "null_resource" "apps" {
  triggers = {
    value = "test-apps-release-notes"
  }
}
