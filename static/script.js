document.getElementById("repoForm").addEventListener("submit", async (event) => {
	event.preventDefault(); // Prevent default form submission

	const repoInput = document.getElementById("repository");
	const submitBtn = document.getElementById("submitBtn");
	const statusDiv = document.getElementById("status");
	const resultsTbody = document.getElementById("resultsTable").querySelector("tbody");
	const repository = repoInput.value.trim();

	if (!repository || !repository.includes("/")) {
		statusDiv.textContent = "Error: Please enter a valid repository in owner/repo format.";
		statusDiv.className = "error";
		return;
	}

	// Clear previous results and status
	resultsTbody.innerHTML = "";
	statusDiv.textContent = "Starting process...";
	statusDiv.className = "loading";
	submitBtn.disabled = true;
	repoInput.disabled = true;

	try {
		const response = await fetch("/generate_emails", {
			method: "POST",
			headers: {
				"Content-Type": "application/json",
			},
			body: JSON.stringify({ repository }),
		});

		if (!response.ok) {
			const errorData = await response.json();
			throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
		}

		// Process the streaming response
		const reader = response.body.getReader();
		const decoder = new TextDecoder(); // To decode UTF-8 stream chunks

		while (true) {
			const { done, value } = await reader.read();
			if (done) {
				// Check if the last status message indicated completion
				if (!statusDiv.textContent.toLowerCase().includes("finished")) {
					statusDiv.textContent = "Stream finished, but final status message missing.";
					statusDiv.className = "warning"; // Or 'success' if appropriate
				} else {
					statusDiv.className = "success"; // Mark as success if finished message received
				}
				break; // Exit loop when stream is done
			}

			// Decode the chunk and process potentially multiple JSON objects within it
			const chunk = decoder.decode(value, { stream: true });
			// Split chunk by newline, as we expect newline-delimited JSON (ndjson)
			const lines = chunk.split("\n").filter((line) => line.trim() !== "");

			lines.forEach((line) => {
				try {
					const data = JSON.parse(line);

					if (data.error) {
						console.error("Stream Error:", data.error);
						statusDiv.textContent = `Error: ${data.error}`;
						statusDiv.className = "error";
						// Optionally break the loop or handle specific errors differently
						// reader.cancel(); // You might want to stop reading on critical errors
					} else if (data.warning) {
						console.warn("Stream Warning:", data.warning);
						// Display warning but continue processing
						statusDiv.textContent = `Warning: ${data.warning}`;
						statusDiv.className = "warning";
					} else if (data.status) {
						console.log("Stream Status:", data.status);
						statusDiv.textContent = data.status;
						statusDiv.className = "loading"; // Keep it loading until 'Finished'
					} else if (data.user && data.email_body) {
						// This is our main data payload
						const newRow = resultsTbody.insertRow();
						newRow.insertCell().textContent = data.user || "N/A";
						newRow.insertCell().textContent = data.name || "N/A";
						newRow.insertCell().textContent = data.email_address || "N/A";
						newRow.insertCell().textContent = data.repo || "N/A";
						// Use pre-wrap to preserve formatting in the email body cell
						const emailCell = newRow.insertCell();
						emailCell.textContent = data.email_body;
						emailCell.style.whiteSpace = "pre-wrap";
						emailCell.style.wordBreak = "break-word"; // Ensure long words wrap

						// Update status to show progress if needed
						statusDiv.textContent = `Processing... Added email for ${data.user}`;
						statusDiv.className = "loading";
					} else {
						console.warn("Received unknown data structure:", data);
					}
				} catch (e) {
					console.error("Error parsing JSON line:", line, e);
					// Decide how to handle parse errors, maybe show a warning
					// statusDiv.textContent = 'Warning: Received malformed data from stream.';
					// statusDiv.className = 'warning';
				}
			});
		}
	} catch (error) {
		console.error("Fetch Error:", error);
		statusDiv.textContent = `Error: ${error.message}`;
		statusDiv.className = "error";
	} finally {
		// Re-enable the form regardless of success or failure
		submitBtn.disabled = false;
		repoInput.disabled = false;
	}
});
