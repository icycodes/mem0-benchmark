import MemoryClient from "mem0ai";
import fs from "fs/promises";
import path from "path";

async function main() {
    const MEM0_API_KEY = process.env.MEM0_API_KEY;
    const ZEALT_RUN_ID = process.env.ZEALT_RUN_ID;

    if (!MEM0_API_KEY || !ZEALT_RUN_ID) {
        console.error("Missing MEM0_API_KEY or ZEALT_RUN_ID");
        process.exit(1);
    }

    const userId = `planner-${ZEALT_RUN_ID}`;
    const client = new MemoryClient({ apiKey: MEM0_API_KEY });

    const notes = [
        {
            messages: [{ "role": "user", "content": "I file my quarterly tax estimates with my accountant every March." }],
            metadata: { "category": "finance", "priority": "high" }
        },
        {
            messages: [{ "role": "user", "content": "I max out my 401(k) contributions early each year." }],
            metadata: { "category": "finance", "priority": "low" }
        },
        {
            messages: [{ "role": "user", "content": "I prefer aisle seats on long-haul flights and direct routes to Tokyo." }],
            metadata: { "category": "travel", "priority": "high" }
        },
        {
            messages: [{ "role": "user", "content": "I run intervals on the treadmill three times a week." }],
            metadata: { "category": "health", "priority": "high" }
        },
        {
            messages: [{ "role": "user", "content": "I take a daily multivitamin in the morning." }],
            metadata: { "category": "health", "priority": "low" }
        }
    ];

    console.log(`Adding ${notes.length} memories...`);
    for (const note of notes) {
        await client.add(note.messages, { userId, metadata: note.metadata });
    }

    // Wait for extraction
    console.log("Waiting for memory extraction...");
    let financeResults = [];
    const financeFilters = {
        AND: [
            { user_id: userId },
            { metadata: { category: "finance" } }
        ]
    };

    // Retry loop for initial ingestion
    for (let i = 0; i < 10; i++) {
        await new Promise(resolve => setTimeout(resolve, 5000));
        console.log(`Polling finance memories (attempt ${i + 1})...`);
        const response = await client.getAll({ filters: financeFilters });
        financeResults = Array.isArray(response) ? response : (response.results || []);
        if (financeResults.length >= 2) break;
    }

    if (financeResults.length < 2) {
        throw new Error(`Failed to ingest finance memories. Found: ${financeResults.length}`);
    }

    const financeArtifact = {
        user_id: userId,
        filter_category: "finance",
        results: financeResults
    };
    await fs.writeFile(path.join("/home/user/mem0-metadata-task", "finance_memories.json"), JSON.stringify(financeArtifact, null, 2));

    // 3. search with v2 compound filter
    const searchFilters = {
        AND: [
            { user_id: userId },
            { metadata: { priority: "high" } }
        ]
    };
    const searchQuery = "Which of my notes are urgent and high priority?";
    
    let searchResults = [];
    for (let i = 0; i < 5; i++) {
        const searchResponse = await client.search(searchQuery, { filters: searchFilters, topK: 20 });
        searchResults = Array.isArray(searchResponse) ? searchResponse : (searchResponse.results || []);
        if (searchResults.length >= 3) break;
        console.log(`Polling high priority memories (attempt ${i + 1})...`);
        await new Promise(resolve => setTimeout(resolve, 3000));
    }

    const searchArtifact = {
        user_id: userId,
        filter_priority: "high",
        results: searchResults
    };
    await fs.writeFile(path.join("/home/user/mem0-metadata-task", "high_priority_search.json"), JSON.stringify(searchArtifact, null, 2));

    // 4. Update and history
    const financeMemoryToUpdate = financeResults.find(m => (m.memory || m.content || "").toLowerCase().includes("tax"));
    const FINANCE_ID = financeMemoryToUpdate.id;
    const updatedText = "Files quarterly tax estimates in March and September with the accountant";
    
    console.log(`Updating memory ${FINANCE_ID}...`);
    // Pass as an object with 'text' property
    await client.update(FINANCE_ID, { text: updatedText });
    
    // Wait for history to reflect
    console.log("Waiting for history update...");
    let history = [];
    for (let i = 0; i < 5; i++) {
        await new Promise(resolve => setTimeout(resolve, 2000));
        history = await client.history(FINANCE_ID);
        if (history.length >= 2) break;
    }

    const historyArtifact = {
        memory_id: FINANCE_ID,
        updated_text: updatedText,
        history: history
    };
    await fs.writeFile(path.join("/home/user/mem0-metadata-task", "finance_history.json"), JSON.stringify(historyArtifact, null, 2));

    // 5. Delete low-priority health memory
    const healthFilters = {
        AND: [
            { user_id: userId },
            { metadata: { category: "health" } }
        ]
    };
    
    let healthResults = [];
    for (let i = 0; i < 5; i++) {
        const healthResponse = await client.getAll({ filters: healthFilters });
        healthResults = Array.isArray(healthResponse) ? healthResponse : (healthResponse.results || []);
        if (healthResults.length >= 2) break;
        await new Promise(resolve => setTimeout(resolve, 3000));
    }

    const multivitaminMemory = healthResults.find(m => (m.memory || m.content || "").toLowerCase().includes("multivitamin"));
    const MULTIVITAMIN_ID = multivitaminMemory.id;

    console.log(`Deleting memory ${MULTIVITAMIN_ID}...`);
    await client.delete(MULTIVITAMIN_ID);

    // Final Log
    console.log(`RUN_ID: ${ZEALT_RUN_ID}`);
    console.log(`USER_ID: ${userId}`);
    console.log(`FINANCE_COUNT: ${financeResults.length}`);
    console.log(`HIGH_PRIORITY_COUNT: ${searchResults.length}`);
    console.log(`FINANCE_ID: ${FINANCE_ID}`);
    console.log(`MULTIVITAMIN_ID: ${MULTIVITAMIN_ID}`);
    console.log(`HISTORY_EVENTS: ${history.length}`);
}

main().catch(err => {
    console.error(err);
    process.exit(1);
});
