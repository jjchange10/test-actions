resource "null_resource" "apps" {
  triggers = {
    value = "test-live-apps-only"
  }
}
