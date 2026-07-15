function sendAishCaseCampaign() {

  const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  const data = sheet.getDataRange().getValues();

  const SUBJECT =
    "Seeking Representation – Civil Rights / Defamation / IIED Case";

  const TEMPLATE = `
Dear {{AttorneyName}},

{{Personalization}}

Message.

Thanks,

User
`;

  // Column J for tracking sent emails
  const SENT_COL = 10;

  for (let i = 0; i < data.length; i++) {

    const row = data[i];

    // Column A = Attorney Name
    const attorneyName = String(row[0] || "").trim();

    // Column H = Personalization sentence
    const personalization = String(row[7] || "").trim();

    // Find email automatically (looks for @ symbol in any column)
    let email = "";
    for (let j = 0; j < row.length; j++) {
      const cell = String(row[j] || "").trim();
      if (
        cell.includes("@") &&
        !cell.includes("linkedin") &&
        !cell.includes("http")
      ) {
        email = cell;
        break;
      }
    }

    // Skip if no email found
    if (!email) continue;

    // Skip if already sent (marked as "SENT" in column J)
    const sentStatus = String(row[SENT_COL - 1] || "").trim();
    if (sentStatus === "SENT") continue;

    // Build email body from template
    const body = TEMPLATE
      .replace("{{AttorneyName}}", attorneyName || "Counsel")
      .replace("{{Personalization}}", personalization);

    try {

      // Send email with BCC to tracking address
      GmailApp.sendEmail(
        email,
        SUBJECT,
        body,
        {
          bcc: "ninagilshteyn@gmail.com"
        }
      );

      // Mark as sent in column J
      sheet.getRange(i + 1, SENT_COL).setValue("SENT");

      Logger.log("Sent to: " + email);

      // 5-second delay between emails (Gmail rate limit)
      Utilities.sleep(5000);

    } catch (err) {

      Logger.log("FAILED: " + email);
      Logger.log(err.toString());
    }
  }

  Logger.log("Campaign complete.");
}
