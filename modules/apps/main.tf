resource "null_resource" "apps" {
  triggers = {
    value = "test-both-apps"
  }
}
