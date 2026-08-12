package com.example;

import java.util.*;

/**
 * Edge case test file for CodeBERT classifier.
 *
 * These functions are deliberately ambiguous — misleading names, mixed patterns,
 * domain-specific language. The old hand-crafted SVM (keyword-based) struggles
 * here. CodeBERT should classify them correctly based on semantic meaning.
 *
 * Expected routing:
 *   rankItems()          → C       (sorting disguised as "ranking")
 *   estimateExposure()   → C       (Monte Carlo disguised as "risk estimation")
 *   buildLookup()        → Rust    (HashMap disguised as "lookup table")
 *   evaluatePortfolio()  → C       (amortization/financial math, no keyword hints)
 *   scoreSequence()      → Rust    (k-mer/hash counting on genomic data)
 *   computeHierarchy()   → C++     (deep recursion, no "recursive" keyword)
 *   loadSettings()       → keep    (I/O, looks like computation due to parsing)
 */
public class EdgeCases {

    // Sorting — but named "rank", no sort/swap/compare keywords
    // Old SVM: likely misses this. CodeBERT: understands ranking = ordering.
    public int[] rankItems(int[] scores) {
        int n = scores.length;
        int[] indices = new int[n];
        for (int i = 0; i < n; i++) indices[i] = i;
        for (int i = 0; i < n - 1; i++) {
            for (int j = 0; j < n - i - 1; j++) {
                if (scores[indices[j]] < scores[indices[j + 1]]) {
                    int tmp = indices[j];
                    indices[j] = indices[j + 1];
                    indices[j + 1] = tmp;
                }
            }
        }
        return indices;
    }

    // Monte Carlo — but called "exposure estimation", no random/gaussian keywords
    // Uses nextDouble instead of nextGaussian, finance domain language
    public double estimateExposure(double notional, double spread, int paths) {
        Random engine = new Random(42);
        double total = 0.0;
        for (int p = 0; p < paths; p++) {
            double scenario = notional;
            for (int step = 0; step < 252; step++) {
                double shock = (engine.nextDouble() - 0.5) * 2 * spread;
                scenario *= (1.0 + shock);
            }
            total += Math.max(scenario - notional, 0.0);
        }
        return total / paths;
    }

    // HashMap counting — but called "buildLookup", generic variable names
    // No hashmap/counter/freq keywords — just registry/entry/tally
    public Map<String, Integer> buildLookup(String[] entries) {
        Map<String, Integer> registry = new LinkedHashMap<>();
        for (String entry : entries) {
            String key = entry.trim().toLowerCase();
            registry.put(key, registry.getOrDefault(key, 0) + 1);
        }
        return registry;
    }

    // Amortization — no loan/mortgage/interest keywords
    // Pure math: declining balance with periodic fixed payment
    public double[] evaluatePortfolio(double face, double couponRate, int periods) {
        double r = couponRate / periods;
        double payment = face * r / (1 - Math.pow(1 + r, -periods));
        double[] cashflows = new double[periods];
        double outstanding = face;
        for (int t = 0; t < periods; t++) {
            double charge = outstanding * r;
            outstanding -= (payment - charge);
            cashflows[t] = payment;
        }
        return cashflows;
    }

    // K-mer / hash_set — but on protein sequences, domain terminology
    // No kmer/nucleotide/dna keywords — uses "residue", "window", "abundance"
    public Map<String, Double> scoreSequence(String protein, int window) {
        Map<String, Integer> abundance = new HashMap<>();
        int total = 0;
        for (int i = 0; i <= protein.length() - window; i++) {
            String residue = protein.substring(i, i + window);
            abundance.merge(residue, 1, Integer::sum);
            total++;
        }
        Map<String, Double> profile = new HashMap<>();
        for (Map.Entry<String, Integer> e : abundance.entrySet()) {
            profile.put(e.getKey(), (double) e.getValue() / total);
        }
        return profile;
    }

    // Deep recursion — no "recursive/tree/node" keywords in name or body
    // Computes org chart depth — looks like business logic
    public int computeHierarchy(Map<String, List<String>> org, String root, int level) {
        List<String> reports = org.getOrDefault(root, Collections.emptyList());
        if (reports.isEmpty()) return level;
        int maxDepth = level;
        for (String report : reports) {
            int depth = computeHierarchy(org, report, level + 1);
            if (depth > maxDepth) maxDepth = depth;
        }
        return maxDepth;
    }

    // I/O — looks computational (parsing, validation) but it's really just I/O
    // Old SVM may route to C due to math-like variable names. Should stay Java.
    public Map<String, Double> loadSettings(String config) {
        Map<String, Double> settings = new HashMap<>();
        for (String line : config.split("\n")) {
            String[] parts = line.split("=");
            if (parts.length == 2) {
                try {
                    settings.put(parts[0].trim(), Double.parseDouble(parts[1].trim()));
                } catch (NumberFormatException ignored) {}
            }
        }
        return settings;
    }
}
