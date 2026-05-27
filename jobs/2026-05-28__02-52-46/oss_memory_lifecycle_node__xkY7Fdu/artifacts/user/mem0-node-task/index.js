import { Memory } from "mem0ai/oss";
import fs from "fs/promises";
import path from "path";
import { createWriteStream } from "fs";

async function main() {
    const runId = process.env.ZEALT_RUN_ID;
    const apiKey = process.env.OPENAI_API_KEY;

    if (!runId) {
        console.error("ZEALT_RUN_ID is missing");
        process.exit(1);
    }

    if (!apiKey) {
        console.error("OPENAI_API_KEY is missing");
        process.exit(1);
    }

    const logFile = "/home/user/mem0-node-task/output.log";
    const logStream = createWriteStream(logFile);

    function log(message) {
        console.log(message);
        logStream.write(message + "\n");
    }

    const aliceId = `alice-${runId}`;
    const bobId = `bob-${runId}`;

    const config = {
        embedder: {
            provider: "openai",
            config: {
                model: "text-embedding-3-small",
                apiKey: apiKey,
            },
        },
        vectorStore: {
            provider: "memory",
            config: {
                collectionName: "memories",
                dimension: 1536,
            },
        },
        llm: {
            provider: "openai",
            config: {
                model: "gpt-4o-mini",
                apiKey: apiKey,
            },
        },
        historyDbPath: "/home/user/mem0-node-task/memory.db",
    };

    const memory = new Memory(config);

    // 1. Ingest conversations
    const aliceMessages = [
        { role: "user", content: "I am vegetarian and I love sourdough bread." },
        { role: "assistant", content: "Noted. I'll save your vegetarian diet and sourdough preference." },
        { role: "user", content: "I also keep a strict no-nuts kitchen for my partner." },
    ];

    const bobMessages = [
        { role: "user", content: "I have a shellfish allergy and I cook a lot of Thai green curry." },
        { role: "assistant", content: "Got it. Logged your shellfish allergy and Thai green curry preference." },
        { role: "user", content: "I always use jasmine rice as the side." },
    ];

    await memory.add(aliceMessages, { userId: aliceId });
    await memory.add(bobMessages, { userId: bobId });

    // 2. Scoped search
    const searchQuery = "What are this cook's dietary preferences?";

    const aliceSearchRaw = await memory.search(searchQuery, { filters: { user_id: aliceId } });
    const aliceResults = Array.isArray(aliceSearchRaw) ? aliceSearchRaw : (aliceSearchRaw.results || []);

    const bobSearchRaw = await memory.search(searchQuery, { filters: { user_id: bobId } });
    const bobResults = Array.isArray(bobSearchRaw) ? bobSearchRaw : (bobSearchRaw.results || []);

    await fs.writeFile(
        "/home/user/mem0-node-task/alice_search.json",
        JSON.stringify({ userId: aliceId, results: aliceResults }, null, 2)
    );
    await fs.writeFile(
        "/home/user/mem0-node-task/bob_search.json",
        JSON.stringify({ userId: bobId, results: bobResults }, null, 2)
    );

    // 3. Update memory
    const aliceMemoriesRaw = await memory.getAll({ filters: { user_id: aliceId } });
    const aliceMemories = Array.isArray(aliceMemoriesRaw) ? aliceMemoriesRaw : (aliceMemoriesRaw.results || []);
    const vegetarianMemory = aliceMemories.find(m => m.memory.toLowerCase().includes("vegetarian"));

    if (!vegetarianMemory) {
        throw new Error("Could not find vegetarian memory for Alice");
    }

    const updatedText = "Alice is vegan and avoids all animal products";
    await memory.update(vegetarianMemory.id, updatedText);

    // 4. History
    const history = await memory.history(vegetarianMemory.id);
    await fs.writeFile(
        "/home/user/mem0-node-task/alice_history.json",
        JSON.stringify(
            {
                memoryId: vegetarianMemory.id,
                updatedText: updatedText,
                history: history,
            },
            null,
            2
        )
    );

    // 5. Output log
    log(`RUN_ID: ${runId}`);
    log(`ALICE_RESULTS: ${aliceResults.length}`);
    log(`BOB_RESULTS: ${bobResults.length}`);
    log(`UPDATED_MEMORY_ID: ${vegetarianMemory.id}`);
    log(`HISTORY_EVENTS: ${history.length}`);

    logStream.end();
}

main().catch(err => {
    console.error(err);
    process.exit(1);
});
