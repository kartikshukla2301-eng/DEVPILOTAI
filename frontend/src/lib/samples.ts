import type { Language } from "./types";

/** Example snippets with deliberate issues, used by the "Load sample" buttons. */
export const REVIEW_SAMPLES: Record<Language, string> = {
  python: `import os
import sqlite3
import pickle

API_KEY = "sk-live-4f9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c"

def getUserOrders(user_id, cache=[]):
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM orders WHERE user_id = {user_id}")
    rows = cur.fetchall()
    report = ""
    for i in range(len(rows)):
        report += str(rows[i]) + "\\n"
    try:
        data = pickle.loads(open("cache.bin", "rb").read())
    except:
        pass
    return report

def average(values):
    return sum(values) / len(values)
`,
  javascript: `const express = require("express");
const { exec } = require("child_process");
var app = express();

app.get("/run", async (req, res) => {
  const cmd = "ls " + req.query.dir;
  exec(cmd, (err, out) => res.send(out));
});

async function loadUsers(ids) {
  const users = [];
  for (let i = 0; i <= ids.length; i++) {
    const u = await fetch("/api/users/" + ids[i]);
    users.push(await u.json());
  }
  if (users.length == 0) console.log("none");
  document.getElementById("list").innerHTML = users.map(u => u.name).join("");
  return users;
}
`,
  typescript: `interface User { id: number; name: string; email?: string }

const password = "SuperSecret123";

export function find_user(users: any[], id: number): User {
  for (let i = 0; i < users.length; i++) {
    if (users[i].id == id) return users[i];
  }
  // @ts-ignore
  return null;
}

export async function saveAll(users: User[]) {
  users.forEach(async (u) => {
    await fetch("/api/users", { method: "POST", body: JSON.stringify(u) });
  });
}
`,
  java: `import java.sql.*;
import java.util.List;
import java.util.ArrayList;

public class UserService {
    public String findUser(Connection conn, String name) throws SQLException {
        Statement st = conn.createStatement();
        ResultSet rs = st.executeQuery("SELECT * FROM users WHERE name = '" + name + "'");
        String result = "";
        while (rs.next()) {
            result += rs.getString("name") + ",";
        }
        if (name == "admin") {
            return "root";
        }
        try {
            Runtime.getRuntime().exec("audit " + name);
        } catch (Exception e) {
            e.printStackTrace();
        }
        return result;
    }
}
`,
  cpp: `#include <iostream>
#include <vector>
#include <cstring>
using namespace std;

int sumAll(vector<int> values) {
    int total = 0;
    for (int i = 0; i <= values.size(); i++) {
        total += values[i];
    }
    return total;
}

int main() {
    char name[16];
    char *buffer = new char[64];
    strcpy(name, "a-very-long-user-name");
    for (int i = 0; i < 1000; i++) {
        cout << i << endl;
    }
    return 0;
}
`,
  c: `#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(void) {
    char input[32];
    char *copy = malloc(64);
    printf("Name: ");
    gets(input);
    strcpy(copy, input);
    printf(input);
    for (int i = 0; i < strlen(input); i++) {
        if (input[i] = 'x') {
            system("echo found");
        }
    }
    return 0;
}
`,
  go: `package main

import (
	"crypto/md5"
	"database/sql"
	"fmt"
	"os"
)

func GetUser(db *sql.DB, id string) {
	query := fmt.Sprintf("SELECT * FROM users WHERE id = '%s'", id)
	rows, _ := db.Query(query)
	for rows.Next() {
		f, err := os.Open("log.txt")
		defer f.Close()
	}
	result := ""
	for i := 0; i < 100; i++ {
		result += fmt.Sprint(i)
	}
	fmt.Println(result)
}
`,
};

export const DEBUG_SAMPLES: Record<Language, { code: string; error: string }> = {
  python: {
    code: `def average(scores):
    total = 0
    for s in scores:
        totl += s
    return total / len(scores)

print(average([90, 85, 77]))
`,
    error: `Traceback (most recent call last):
  File "main.py", line 7, in <module>
    print(average([90, 85, 77]))
  File "main.py", line 4, in average
    totl += s
NameError: name 'totl' is not defined`,
  },
  javascript: {
    code: `async function showProfile(api) {
  const res = await api.get("/me");
  const city = res.data.address.city;
  console.log(city.toUpperCase());
}
`,
    error: `TypeError: Cannot read properties of undefined (reading 'city')
    at showProfile (/app/profile.js:3:34)`,
  },
  typescript: {
    code: `function total(items: number[]): number {
  let sum: number = "0";
  for (const i of items) sum += i;
  return sum;
}
`,
    error: `src/total.ts(2,7): error TS2322: Type 'string' is not assignable to type 'number'.`,
  },
  java: {
    code: `public class Main {
    public static void main(String[] args) {
        int[] values = {1, 2, 3};
        for (int i = 0; i <= values.length; i++) {
            System.out.println(values[i]);
        }
    }
}
`,
    error: `Exception in thread "main" java.lang.ArrayIndexOutOfBoundsException: Index 3 out of bounds for length 3
	at Main.main(Main.java:5)`,
  },
  cpp: {
    code: `#include <iostream>
int main() {
    int count = 5
    std::cout << count << std::endl;
    return 0;
}
`,
    error: `main.cpp: In function 'int main()':
main.cpp:4:5: error: expected ',' or ';' before 'std'`,
  },
  c: {
    code: `#include <stdio.h>
int main(void) {
    int *p = NULL;
    *p = 42;
    printf("%d\\n", *p);
    return 0;
}
`,
    error: `Segmentation fault (core dumped)`,
  },
  go: {
    code: `package main

import (
	"fmt"
	"strings"
)

func main() {
	fmt.Println("hello")
}
`,
    error: `./main.go:5:2: "strings" imported and not used`,
  },
};

export const EXPLAIN_SAMPLE: Record<Language, string> = {
  python: `def binary_search(items, target):
    """Return the index of target in a sorted list, or -1."""
    low, high = 0, len(items) - 1
    while low <= high:
        mid = (low + high) // 2
        if items[mid] == target:
            return mid
        elif items[mid] < target:
            low = mid + 1
        else:
            high = mid - 1
    return -1

print(binary_search([1, 3, 5, 7, 9], 7))
`,
  javascript: `function twoSum(nums, target) {
  const seen = new Map();
  for (let i = 0; i < nums.length; i++) {
    const need = target - nums[i];
    if (seen.has(need)) return [seen.get(need), i];
    seen.set(nums[i], i);
  }
  return [];
}
console.log(twoSum([2, 7, 11, 15], 9));
`,
  typescript: `type Node = { value: number; children: Node[] };

export function sumTree(node: Node): number {
  let total = node.value;
  for (const child of node.children) {
    total += sumTree(child);
  }
  return total;
}
`,
  java: `public class Fib {
    static long fib(int n) {
        if (n < 2) return n;
        return fib(n - 1) + fib(n - 2);
    }
    public static void main(String[] args) {
        System.out.println(fib(10));
    }
}
`,
  cpp: `#include <vector>
#include <algorithm>

int maxSubarray(const std::vector<int>& a) {
    int best = a[0], cur = a[0];
    for (size_t i = 1; i < a.size(); ++i) {
        cur = std::max(a[i], cur + a[i]);
        best = std::max(best, cur);
    }
    return best;
}
`,
  c: `#include <stdio.h>

void bubble_sort(int a[], int n) {
    for (int i = 0; i < n - 1; i++) {
        for (int j = 0; j < n - i - 1; j++) {
            if (a[j] > a[j + 1]) {
                int t = a[j];
                a[j] = a[j + 1];
                a[j + 1] = t;
            }
        }
    }
}
`,
  go: `package main

import "fmt"

func reverse(s []int) []int {
	out := make([]int, 0, len(s))
	for i := len(s) - 1; i >= 0; i-- {
		out = append(out, s[i])
	}
	return out
}

func main() {
	fmt.Println(reverse([]int{1, 2, 3}))
}
`,
};
