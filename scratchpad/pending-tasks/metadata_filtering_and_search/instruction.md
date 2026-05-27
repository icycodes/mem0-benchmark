You need to implement a Python script that stores memories with custom metadata and retrieves them using hybrid search filters. Add two memories for `user_id="traveler"`: "I loved the beaches in Hawaii" with attached metadata `{"category": "travel", "year": 2022}`, and "I want to visit the Alps" with attached metadata `{"category": "travel", "year": 2024}`. Perform a search for "travel destinations" applying a filter to only retrieve memories where the year is 2024.

**Constraints:**
- The search operation must strictly apply the dictionary filter for `year == 2024`.
- Output the content of the filtered, retrieved memory to standard output.
- Do NOT retrieve or print the memory from 2022.