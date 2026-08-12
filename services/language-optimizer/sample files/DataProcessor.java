package com.example;

import java.util.*;

/**
 * Test file for Rust recommendation verification.
 * Contains HashMap counting and binary tree functions
 * that should be recommended for Rust conversion.
 */
public class DataProcessor {

    // HashMap counting — should recommend Rust
    public Map<String, Integer> countWordFrequency(String[] words) {
        Map<String, Integer> freq = new HashMap<>();
        for (String word : words) {
            freq.merge(word.toLowerCase(), 1, Integer::sum);
        }
        return freq;
    }

    // K-mer counting — should recommend Rust
    public Map<String, Integer> countKmers(String sequence, int k) {
        Map<String, Integer> counts = new HashMap<>();
        for (int i = 0; i <= sequence.length() - k; i++) {
            String kmer = sequence.substring(i, i + k);
            counts.merge(kmer, 1, Integer::sum);
        }
        return counts;
    }

    // Binary tree operations — should recommend Rust
    public int computeTreeDepth(TreeNode root) {
        if (root == null) return 0;
        return 1 + Math.max(
            computeTreeDepth(root.left),
            computeTreeDepth(root.right)
        );
    }

    // Tree sum — should recommend Rust
    public long sumTreeValues(TreeNode root) {
        if (root == null) return 0;
        return root.val + sumTreeValues(root.left) + sumTreeValues(root.right);
    }

    // Orchestration — should stay in Java
    public void processData(String[] words, String sequence, TreeNode tree) {
        Map<String, Integer> wordFreq = countWordFrequency(words);
        Map<String, Integer> kmers    = countKmers(sequence, 3);
        int depth = computeTreeDepth(tree);
        long sum  = sumTreeValues(tree);
        System.out.println("Words: " + wordFreq.size() +
                           " Kmers: " + kmers.size() +
                           " Depth: " + depth +
                           " Sum: " + sum);
    }

    public static class TreeNode {
        public int val;
        public TreeNode left, right;
        public TreeNode(int val) { this.val = val; }
    }
}
