globalThis.window = {
  crypto: globalThis.crypto
};

import fs from 'fs';
import path from 'path';
import MemoryClient from 'mem0ai';

// Helper function to normalize SDK responses
function normalizeResponse(res) {
  if (!res) return [];
  if (Array.isArray(res)) return res;
  if (res && Array.isArray(res.results)) return res.results;
  if (res && Array.isArray(res.memories)) return res.memories;
  return [];
}

async function main() {
  console.log("Starting Mem0 Platform metadata task...");

  // 1. Validate environment variables
  const apiKey = process.env.MEM0_API_KEY;
  const runId = process.env.ZEALT_RUN_ID;

  if (!apiKey) {
    console.error("Error: MEM0_API_KEY is missing in process.env");
    process.exit(1);
  }
  if (!runId) {
    console.error("Error: ZEALT_RUN_ID is missing in process.env");
    process.exit(1);
  }

  const userId = `planner-${runId}`;
  console.log(`RUN_ID: ${runId}`);
  console.log(`USER_ID: ${userId}`);

  // 2. Initialize MemoryClient
  const client = new MemoryClient({ apiKey });

  // 3. Ingest five notes
  const notes = [
    {
      messages: [{"role": "user", "content": "I file my quarterly tax estimates with my accountant every March."}],
      metadata: {"category": "finance", "priority": "high"}
    },
    {
      messages: [{"role": "user", "content": "I max out my 401(k) contributions early each year."}],
      metadata: {"category": "finance", "priority": "low"}
    },
    {
      messages: [{"role": "user", "content": "I prefer aisle seats on long-haul flights and direct routes to Tokyo."}],
      metadata: {"category": "travel", "priority": "high"}
    },
    {
      messages: [{"role": "user", "content": "I run intervals on the treadmill three times a week."}],
      metadata: {"category": "health", "priority": "high"}
    },
    {
      messages: [{"role": "user", "content": "I take a daily multivitamin in the morning."}],
      metadata: {"category": "health", "priority": "low"}
    }
  ];

  console.log("Ingesting 5 memories...");
  for (let i = 0; i < notes.length; i++) {
    const note = notes[i];
    console.log(`Adding memory ${i + 1}/5: "${note.messages[0].content}"`);
    const addRes = await client.add(note.messages, {
      userId: userId,
      user_id: userId,
      metadata: note.metadata
    });
    console.log("Add response:", JSON.stringify(addRes));
  }

  // 4. Poll until memories are fully indexed
  console.log("Waiting for memories to be fully indexed on the platform...");
  let allMemories = [];
  let financeResults = [];
  let highPriorityResults = [];

  // We will poll up to 30 times with a 3-second delay (90 seconds max)
  for (let i = 0; i < 30; i++) {
    try {
      const allRes = await client.getAll({
        filters: {
          AND: [
            { user_id: userId }
          ]
        },
        api_version: "v2"
      });
      allMemories = normalizeResponse(allRes);

      const finRes = await client.getAll({
        filters: {
          AND: [
            { user_id: userId },
            { metadata: { category: "finance" } }
          ]
        },
        api_version: "v2"
      });
      financeResults = normalizeResponse(finRes);

      const hpRes = await client.getAll({
        filters: {
          AND: [
            { user_id: userId },
            { metadata: { priority: "high" } }
          ]
        },
        api_version: "v2"
      });
      highPriorityResults = normalizeResponse(hpRes);

      console.log(`Poll ${i + 1}: Total=${allMemories.length}, Finance=${financeResults.length}, HighPriority=${highPriorityResults.length}`);

      if (allMemories.length >= 5 && financeResults.length >= 2 && highPriorityResults.length >= 3) {
        console.log("All memories successfully indexed!");
        break;
      }
    } catch (err) {
      console.error("Error during polling:", err.message);
    }
    await new Promise(resolve => setTimeout(resolve, 3000));
  }

  // Double check that we have the required counts
  const financeCount = financeResults.length;
  const highPriorityCount = highPriorityResults.length;

  console.log(`Final Finance Count: ${financeCount}`);
  console.log(`Final High Priority Count: ${highPriorityCount}`);

  // 5. Persist finance memories
  const financeMemoriesPath = '/home/user/mem0-metadata-task/finance_memories.json';
  const financeMemoriesPayload = {
    user_id: userId,
    filter_category: "finance",
    results: financeResults
  };
  fs.writeFileSync(financeMemoriesPath, JSON.stringify(financeMemoriesPayload, null, 2));
  console.log(`Saved ${financeMemoriesPath}`);

  // 6. Perform semantic search for high priority memories
  console.log("Performing high priority search...");
  const searchQuery = "Which of my notes are urgent and high priority?";
  const searchRes = await client.search(searchQuery, {
    filters: {
      AND: [
        { user_id: userId },
        { metadata: { priority: "high" } }
      ]
    },
    topK: 20,
    api_version: "v2"
  });
  const searchResults = normalizeResponse(searchRes);
  console.log(`Search returned ${searchResults.length} results.`);

  const highPrioritySearchPath = '/home/user/mem0-metadata-task/high_priority_search.json';
  const highPrioritySearchPayload = {
    user_id: userId,
    filter_priority: "high",
    results: searchResults
  };
  fs.writeFileSync(highPrioritySearchPath, JSON.stringify(highPrioritySearchPayload, null, 2));
  console.log(`Saved ${highPrioritySearchPath}`);

  // 7. Pick finance memory with "tax", update it, and fetch history
  const financeMemoryWithTax = financeResults.find(m => {
    const text = m.memory || m.text || m.content || "";
    return text.toLowerCase().includes("tax");
  });

  if (!financeMemoryWithTax) {
    throw new Error("Could not find finance memory containing 'tax'");
  }

  const FINANCE_ID = financeMemoryWithTax.id;
  console.log(`Found FINANCE_ID: ${FINANCE_ID}`);

  const updatedText = "Files quarterly tax estimates in March and September with the accountant";
  console.log(`Updating memory ${FINANCE_ID} with text: "${updatedText}"`);
  const updateRes = await client.update(FINANCE_ID, updatedText);
  console.log("Update response:", JSON.stringify(updateRes));

  // Wait/poll for history to reflect the update event
  console.log("Waiting for memory history to reflect the update...");
  let historyEvents = [];
  for (let i = 0; i < 15; i++) {
    try {
      const historyRes = await client.history(FINANCE_ID);
      console.log(`History response details (poll ${i + 1}):`, JSON.stringify(historyRes));
      
      let tempEvents = [];
      if (Array.isArray(historyRes)) {
        tempEvents = historyRes;
      } else if (historyRes && Array.isArray(historyRes.history)) {
        tempEvents = historyRes.history;
      } else if (historyRes && Array.isArray(historyRes.results)) {
        tempEvents = historyRes.results;
      } else if (historyRes) {
        tempEvents = [historyRes];
      }

      const hasUpdateEvent = tempEvents.some(event => {
        const typeField = event.event || event.type || event.action || "";
        return typeField.toUpperCase().includes("UPDATE");
      });

      if (tempEvents.length >= 2 && hasUpdateEvent) {
        historyEvents = tempEvents;
        console.log("History successfully contains at least 2 events including UPDATE!");
        break;
      }
    } catch (err) {
      console.error("Error fetching history:", err.message);
    }
    await new Promise(resolve => setTimeout(resolve, 2000));
  }

  const historyEventsCount = historyEvents.length;
  console.log(`History events count: ${historyEventsCount}`);

  const financeHistoryPath = '/home/user/mem0-metadata-task/finance_history.json';
  const financeHistoryPayload = {
    memory_id: FINANCE_ID,
    updated_text: updatedText,
    history: historyEvents
  };
  fs.writeFileSync(financeHistoryPath, JSON.stringify(financeHistoryPayload, null, 2));
  console.log(`Saved ${financeHistoryPath}`);

  // 8. Find low-priority health memory (contains "multivitamin") and delete it
  const healthLowPriorityMemory = allMemories.find(m => {
    const text = (m.memory || m.text || m.content || "").toLowerCase();
    const isHealth = m.metadata && m.metadata.category === "health";
    const isLow = m.metadata && m.metadata.priority === "low";
    return text.includes("multivitamin") || (isHealth && isLow);
  });

  if (!healthLowPriorityMemory) {
    throw new Error("Could not find health memory containing 'multivitamin' or category=health & priority=low");
  }

  const MULTIVITAMIN_ID = healthLowPriorityMemory.id;
  console.log(`Found MULTIVITAMIN_ID: ${MULTIVITAMIN_ID}`);

  console.log(`Deleting memory ${MULTIVITAMIN_ID}...`);
  const deleteRes = await client.delete(MULTIVITAMIN_ID);
  console.log("Delete response:", JSON.stringify(deleteRes));

  // Wait a few seconds for the deletion to propagate
  await new Promise(resolve => setTimeout(resolve, 4000));

  // 9. Verify server-side effects using a fresh client
  console.log("Verifying server-side effects with a fresh client...");
  const verifyClient = new MemoryClient({ apiKey });

  // Verification 1: Finance memories should contain updated text with "September"
  const verifyFinRes = await verifyClient.getAll({
    filters: {
      AND: [
        { user_id: userId },
        { metadata: { category: "finance" } }
      ]
    },
    api_version: "v2"
  });
  const verifyFin = normalizeResponse(verifyFinRes);
  const hasSeptember = verifyFin.some(m => {
    const text = m.memory || m.text || m.content || "";
    return text.toLowerCase().includes("september");
  });
  console.log(`Verification - Finance contains 'September': ${hasSeptember}`);

  // Verification 2: Health memories should NOT contain "multivitamin"
  const verifyHealthRes = await verifyClient.getAll({
    filters: {
      AND: [
        { user_id: userId },
        { metadata: { category: "health" } }
      ]
    },
    api_version: "v2"
  });
  const verifyHealth = normalizeResponse(verifyHealthRes);
  const hasMultivitamin = verifyHealth.some(m => {
    const text = m.memory || m.text || m.content || "";
    return text.toLowerCase().includes("multivitamin");
  });
  console.log(`Verification - Health contains 'multivitamin': ${hasMultivitamin}`);

  // Verification 3: Travel memories should contain "Tokyo"
  const verifyTravelRes = await verifyClient.getAll({
    filters: {
      AND: [
        { user_id: userId },
        { metadata: { category: "travel" } }
      ]
    },
    api_version: "v2"
  });
  const verifyTravel = normalizeResponse(verifyTravelRes);
  const hasTokyo = verifyTravel.some(m => {
    const text = m.memory || m.text || m.content || "";
    return text.toLowerCase().includes("tokyo");
  });
  console.log(`Verification - Travel contains 'Tokyo': ${hasTokyo}`);

  // 10. Print required output.log content to stdout
  const outputLogLines = [
    `RUN_ID: ${runId}`,
    `USER_ID: ${userId}`,
    `FINANCE_COUNT: ${financeCount}`,
    `HIGH_PRIORITY_COUNT: ${highPriorityCount}`,
    `FINANCE_ID: ${FINANCE_ID}`,
    `MULTIVITAMIN_ID: ${MULTIVITAMIN_ID}`,
    `HISTORY_EVENTS: ${historyEventsCount}`
  ];

  console.log("\n--- REQUIRED OUTPUT LOG ---");
  outputLogLines.forEach(line => console.log(line));
  console.log("---------------------------\n");

  const outputLogPath = '/home/user/mem0-metadata-task/output.log';
  fs.writeFileSync(outputLogPath, outputLogLines.join('\n') + '\n');
  console.log(`Saved output log to ${outputLogPath}`);

  console.log("All tasks completed successfully!");
}

main().catch(err => {
  console.error("Fatal error in main:", err);
  process.exit(1);
});
