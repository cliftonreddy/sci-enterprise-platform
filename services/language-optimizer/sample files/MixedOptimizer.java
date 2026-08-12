package com.example;

import java.util.*;

/**
 * MixedOptimizer.java
 * Sample file to demonstrate C, C++, and Rust recommendations.
 *
 * Expected results:
 *   sortPrices()          → C      (sorting, ~52%)
 *   runSimulation()       → C      (Monte Carlo, ~56%)
 *   computeAmortization() → C      (numeric iteration, ~52%)
 *   evaluateRisk()        → C++    (deep recursion, ~40%)
 *   countFrequency()      → Rust   (HashMap counting, ~51%)
 *   buildIndex()          → Rust   (tree/hash structure, ~51%)
 *   loadConfig()          → keep   (I/O)
 *   orchestrate()         → keep   (orchestration)
 */
public class MixedOptimizer {

    // ── C target: sorting ─────────────────────────────────────────────────────
    public double[] sortPrices(double[] prices) {
        double[] sorted = prices.clone();
        int n = sorted.length;
        for (int i = 0; i < n - 1; i++) {
            for (int j = 0; j < n - i - 1; j++) {
                if (sorted[j] > sorted[j + 1]) {
                    double tmp = sorted[j];
                    sorted[j] = sorted[j + 1];
                    sorted[j + 1] = tmp;
                }
            }
        }
        return sorted;
    }

    // ── C target: Monte Carlo simulation ──────────────────────────────────────
    public double runSimulation(double portfolioValue, double volatility,
            int simulations, int horizon) {
        Random rng = new Random(42);
        double[] results = new double[simulations];
        double dt = 1.0 / 252.0;
        for (int s = 0; s < simulations; s++) {
            double value = portfolioValue;
            for (int d = 0; d < horizon; d++) {
                double z = rng.nextGaussian();
                value *= Math.exp(-0.5 * volatility * volatility * dt
                        + volatility * Math.sqrt(dt) * z);
            }
            results[s] = value;
        }
        Arrays.sort(results);
        return results[(int) (simulations * 0.05)];
    }

    // ── C target: amortization ────────────────────────────────────────────────
    public double computeAmortization(double principal, double annualRate,
            int months) {
        double r = annualRate / 12.0 / 100.0;
        double payment = principal * r / (1 - Math.pow(1 + r, -months));
        double balance = principal;
        double totalInterest = 0;
        for (int m = 1; m <= months; m++) {
            double interest = balance * r;
            totalInterest += interest;
            balance -= payment - interest;
        }
        return totalInterest;
    }

    // ── C++ target: deep recursion ────────────────────────────────────────────
    public double evaluateRisk(double[] factors, double[] weights, int depth) {
        if (depth == 0 || factors.length <= 1) {
            double score = 0;
            for (int i = 0; i < factors.length; i++)
                score += factors[i] * weights[i];
            return score;
        }
        int mid = factors.length / 2;
        double left = evaluateRisk(
            Arrays.copyOfRange(factors, 0, mid),
            Arrays.copyOfRange(weights, 0, mid), depth - 1);
        double right = evaluateRisk(
            Arrays.copyOfRange(factors, mid, factors.length),
            Arrays.copyOfRange(weights, mid, weights.length), depth - 1);
        return (left + right) / 2.0;
    }

    // ── Rust target: HashMap counting ────────────────────────────────────────
    public Map<String, Integer> countFrequency(String[] tokens) {
        Map<String, Integer> freq = new HashMap<>();
        for (String token : tokens) {
            freq.merge(token.toLowerCase(), 1, Integer::sum);
        }
        return freq;
    }

    // ── Rust target: tree/index structure ────────────────────────────────────
    public Map<String, List<Integer>> buildIndex(String[] words, int[] positions) {
        Map<String, List<Integer>> index = new HashMap<>();
        for (int i = 0; i < words.length; i++) {
            index.computeIfAbsent(words[i], k -> new ArrayList<>()).add(positions[i]);
        }
        return index;
    }

    // ── keep: I/O ─────────────────────────────────────────────────────────────
    public Properties loadConfig(String path) throws Exception {
        Properties props = new Properties();
        try (java.io.FileInputStream fis = new java.io.FileInputStream(path)) {
            props.load(fis);
        }
        return props;
    }

    // ── keep: orchestration ───────────────────────────────────────────────────
    public void orchestrate(double[] prices, double[] factors, String[] tokens) {
        double[] sorted    = sortPrices(prices);
        double   var95     = runSimulation(10000, 0.2, 100000, 252);
        double   interest  = computeAmortization(250000, 6.5, 360);
        double   riskScore = evaluateRisk(factors, factors, 3);
        Map<String, Integer> freq = countFrequency(tokens);
        System.out.printf("Sorted[0]=%.2f VaR=%.2f Interest=%.2f Risk=%.4f Tokens=%d%n",
            sorted[0], var95, interest, riskScore, freq.size());
    }
}
