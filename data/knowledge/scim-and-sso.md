# SCIM Provisioning and SSO Setup

Tasklet supports SAML-based single sign-on and SCIM for automated user provisioning.

## SAML SSO

1. Go to Settings > Security > SSO.
2. Enter your Identity Provider (IdP) metadata URL or upload the XML file.
3. Copy the Tasklet ACS URL and Entity ID into your IdP configuration.
4. Test the connection, then enable SSO.

If your IdP rotates the metadata URL, update it under Settings > Security > SSO > Edit Connection.

## SCIM with Okta

1. In Okta, add the Tasklet SCIM app from the directory.
2. Under Provisioning, enter the Tasklet SCIM endpoint: `https://api.tasklet.example/scim/v2`.
3. Enter your SCIM bearer token (generate one under Settings > Security > API Tokens).
4. Enable Create Users, Update Users, and Deactivate Users.

If you see "invalid metadata" on the Okta side, regenerate the SCIM token in Tasklet and re-enter it in Okta. Tokens expire after 90 days.

## Troubleshooting

If SAML login fails after IdP changes, verify the metadata URL and ACS URL match. If SCIM sync stops, check that the bearer token has not expired.
