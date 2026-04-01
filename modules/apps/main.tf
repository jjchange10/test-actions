resource "null_resource" "apps" {
  triggers = {
    value = "test-cumulative-live-apps-only"
  }
}
