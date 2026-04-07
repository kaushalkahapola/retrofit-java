# Transition Summary

- Source: phase_outputs
- Valid backport signal: True
- Reason: Valid: Observed fail-to-pass and/or newly passing relevant tests with no regressions.
- fail->pass (0): []
- newly passing (29): ['io.crate.role.TransportRoleActionTest#testCreateFirstUser', 'io.crate.role.TransportRoleActionTest#testCreateUser', 'io.crate.role.TransportRoleActionTest#testCreateUserAlreadyExists', 'io.crate.role.TransportRoleActionTest#testDropNonExistingUser', 'io.crate.role.TransportRoleActionTest#testDropUser', 'io.crate.role.TransportRoleActionTest#testDropUserNoUsersAtAll', 'io.crate.role.TransportRoleActionTest#test_alter_user_cannot_set_jwt_to_role', 'io.crate.role.TransportRoleActionTest#test_alter_user_cannot_set_password_to_role', 'io.crate.role.TransportRoleActionTest#test_alter_user_change_jwt_and_keep_password', 'io.crate.role.TransportRoleActionTest#test_alter_user_change_or_reset_password_and_keep_jwt', 'io.crate.role.TransportRoleActionTest#test_alter_user_reset_jwt_and_password', 'io.crate.role.TransportRoleActionTest#test_alter_user_throws_error_on_jwt_properties_clash', 'io.crate.role.TransportRoleActionTest#test_alter_user_with_old_users_metadata', 'io.crate.role.TransportRoleActionTest#test_cannot_drop_user_mapped_to_foreign_servers', 'io.crate.role.TransportRoleActionTest#test_create_user_with_existing_name_but_different_jwt_props', 'io.crate.role.TransportRoleActionTest#test_create_user_with_matching_jwt_props_exists', 'io.crate.role.TransportRoleActionTest#test_create_user_with_old_users_metadata', 'io.crate.role.TransportRoleActionTest#test_drop_role_with_children_is_not_allowed', 'io.crate.role.TransportRoleActionTest#test_drop_user_with_old_users_metadata', 'io.crate.role.metadata.RolesMetadataTest#test_add_old_users_metadata_to_roles_metadata', 'io.crate.role.metadata.RolesMetadataTest#test_grant_roles_do_not_loose_existing_privileges', 'io.crate.role.metadata.RolesMetadataTest#test_grant_roles_to_user', 'io.crate.role.metadata.RolesMetadataTest#test_jwt_properties_from_invalid_x_content', 'io.crate.role.metadata.RolesMetadataTest#test_revoke_roles_from_user', 'io.crate.role.metadata.RolesMetadataTest#test_roles_metadata_from_cluster_state', 'io.crate.role.metadata.RolesMetadataTest#test_roles_metadata_streaming', 'io.crate.role.metadata.RolesMetadataTest#test_roles_metadata_to_x_content', 'io.crate.role.metadata.RolesMetadataTest#test_roles_metadata_with_attributes_streaming', 'io.crate.role.metadata.RolesMetadataTest#test_roles_metadata_without_attributes_to_xcontent']
- pass->fail (0): []

## Touched Test States
- Touched tests (from patch): ['io.crate.role.TransportRoleActionTest', 'io.crate.role.metadata.RolesMetadataTest']
  - io.crate.role.TransportRoleActionTest#testCreateFirstUser: baseline=absent, patched=passed
  - io.crate.role.TransportRoleActionTest#testCreateUser: baseline=absent, patched=passed
  - io.crate.role.TransportRoleActionTest#testCreateUserAlreadyExists: baseline=absent, patched=passed
  - io.crate.role.TransportRoleActionTest#testDropNonExistingUser: baseline=absent, patched=passed
  - io.crate.role.TransportRoleActionTest#testDropUser: baseline=absent, patched=passed
  - io.crate.role.TransportRoleActionTest#testDropUserNoUsersAtAll: baseline=absent, patched=passed
  - io.crate.role.TransportRoleActionTest#test_alter_user_cannot_set_jwt_to_role: baseline=absent, patched=passed
  - io.crate.role.TransportRoleActionTest#test_alter_user_cannot_set_password_to_role: baseline=absent, patched=passed
  - io.crate.role.TransportRoleActionTest#test_alter_user_change_jwt_and_keep_password: baseline=absent, patched=passed
  - io.crate.role.TransportRoleActionTest#test_alter_user_change_or_reset_password_and_keep_jwt: baseline=absent, patched=passed
  - io.crate.role.TransportRoleActionTest#test_alter_user_reset_jwt_and_password: baseline=absent, patched=passed
  - io.crate.role.TransportRoleActionTest#test_alter_user_throws_error_on_jwt_properties_clash: baseline=absent, patched=passed
  - io.crate.role.TransportRoleActionTest#test_alter_user_with_old_users_metadata: baseline=absent, patched=passed
  - io.crate.role.TransportRoleActionTest#test_cannot_drop_user_mapped_to_foreign_servers: baseline=absent, patched=passed
  - io.crate.role.TransportRoleActionTest#test_create_user_with_existing_name_but_different_jwt_props: baseline=absent, patched=passed
  - io.crate.role.TransportRoleActionTest#test_create_user_with_matching_jwt_props_exists: baseline=absent, patched=passed
  - io.crate.role.TransportRoleActionTest#test_create_user_with_old_users_metadata: baseline=absent, patched=passed
  - io.crate.role.TransportRoleActionTest#test_drop_role_with_children_is_not_allowed: baseline=absent, patched=passed
  - io.crate.role.TransportRoleActionTest#test_drop_user_with_old_users_metadata: baseline=absent, patched=passed
  - io.crate.role.metadata.RolesMetadataTest#test_add_old_users_metadata_to_roles_metadata: baseline=absent, patched=passed
  - io.crate.role.metadata.RolesMetadataTest#test_grant_roles_do_not_loose_existing_privileges: baseline=absent, patched=passed
  - io.crate.role.metadata.RolesMetadataTest#test_grant_roles_to_user: baseline=absent, patched=passed
  - io.crate.role.metadata.RolesMetadataTest#test_jwt_properties_from_invalid_x_content: baseline=absent, patched=passed
  - io.crate.role.metadata.RolesMetadataTest#test_revoke_roles_from_user: baseline=absent, patched=passed
  - io.crate.role.metadata.RolesMetadataTest#test_roles_metadata_from_cluster_state: baseline=absent, patched=passed
  - io.crate.role.metadata.RolesMetadataTest#test_roles_metadata_streaming: baseline=absent, patched=passed
  - io.crate.role.metadata.RolesMetadataTest#test_roles_metadata_to_x_content: baseline=absent, patched=passed
  - io.crate.role.metadata.RolesMetadataTest#test_roles_metadata_with_attributes_streaming: baseline=absent, patched=passed
  - io.crate.role.metadata.RolesMetadataTest#test_roles_metadata_without_attributes_to_xcontent: baseline=absent, patched=passed
