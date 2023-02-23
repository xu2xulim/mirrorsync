This is a 2 way one-to-one mirror and sync solution for Trello that uses Trello native webhooks. It is implemented with FASTAPI to provide the api services for both the setup and actual mirror-sync operations. Since it uses the admin user's API Key and Token, the operations can be across any workspace or boards that are accessible by the admin user's credentials.

## Scope
The scope for the mirror and synchronization operations include :

- Name and description
- Due Date and Time, Start Date, due Reminder etc
- Labels (including custom labels)
- Checklists (Supports advanced checklist due date and member assignment with Advanced Checklist)
- Customfields
- Locations (Support available. Location requires a minimum of a Standard plan)
- Attachments (also 3rd party attachments like Box, Trello card / board, images, pdf...etc)
- Comments (not activated at this moment)

## Notes on board specific features
For custom fields and labels work properly, the boards must have the right setup especially when the copy is moved or sent to another board. To ensure this is properly setup create a dummy card with all the labels and custom fields and move it to the designation board. Trello will handle the setup on the second board. The dummy card can then be deleted.

Documentation on this app is available at [milynnus Blog-Doc](https://milynnus_blogdoc-1-v8438569.deta.app "‌") under the tag **MirrorSync**